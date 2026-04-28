"""End-to-end reproduction script for the 2026-04-28 demo bugs.

Mirrors the screenshots:
  1. Three users (Alice, Bob, Dave) each with a Claude agent connected.
  2. Dave types "改一下db.py, 新增个1000行 print('hello world')".
  3. Dave's relay subprocess fakes the content-filter failure path:
     announce_intent succeeds, then write_project_file raises and the
     subprocess exits 1 BEFORE calling withdraw_intent.
  4. Dave types the same prompt again (a real-life retry).

Pre-fix observation: Dave's first orphan intent + Dave's retry intent
collide, producing a "Dave's Claude ↔ Dave's Claude" CONFLICT_REPORT.
Plus, when Alice arrives later the conflicts get tangled.

Post-fix expectation:
  * Coordinator never produces a same-principal CONFLICT_REPORT.
  * Dave's retry auto-supersedes the orphan; only one Dave intent is
    ACTIVE at any time.
  * When Alice announces after Dave's retry, the conflict references
    Dave's RETRY intent (not the dead orphan).

Run with::

    .venv/bin/python scripts/repro_self_conflict_2026-04-28.py

Exit code 0 = all assertions passed.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mpac-package" / "src"))
sys.path.insert(0, str(REPO_ROOT / "web-app"))

from api.mpac_bridge import (  # noqa: E402
    ProjectSession,
    _ConnectedParticipant,
    process_envelope,
)
from mpac_protocol.core.coordinator import SessionCoordinator  # noqa: E402
from mpac_protocol.core.models import IntentState, Scope  # noqa: E402
from mpac_protocol.core.participant import Participant  # noqa: E402


def _make_participant(principal_id: str, display_name: str) -> Participant:
    return Participant(
        principal_id=principal_id,
        principal_type="agent",
        display_name=display_name,
        roles=["contributor"],
        capabilities=["intent.broadcast", "op.commit"],
    )


def _make_send(received: Dict[str, List[Dict[str, Any]]], principal_id: str):
    async def send(envelope: Dict[str, Any]) -> None:
        received.setdefault(principal_id, []).append(envelope)
    return send


async def _setup_session():
    session_id = "demo-session"
    session = ProjectSession(
        project_id=1,
        mpac_session_id=session_id,
        coordinator=SessionCoordinator(
            session_id=session_id, security_profile="open",
        ),
    )
    received: Dict[str, List[Dict[str, Any]]] = {}
    participants = {
        "agent:user-1": _make_participant(
            "agent:user-1", "Alice's Claude",
        ),
        "agent:user-2": _make_participant("agent:user-2", "Bob's Claude"),
        "agent:user-3": _make_participant("agent:user-3", "Dave's Claude"),
    }
    for pid, p in participants.items():
        received[pid] = []
        session.connections[pid] = _ConnectedParticipant(
            principal_id=pid,
            participant=p,
            send=_make_send(received, pid),
            display_name=p.display_name,
            principal_type=p.principal_type,
            roles=p.roles,
            is_agent=True,
        )
        session.coordinator.process_message(p.hello(session_id))
    return session, participants, received


async def _announce(session, participants, received, pid, intent_id, files,
                    objective):
    # Reset received buffer to make conflict assertions easier.
    for buf in received.values():
        buf.clear()
    scope = Scope(kind="file_set", resources=files)
    await process_envelope(
        session,
        participants[pid].announce_intent(
            session_id=session.mpac_session_id,
            intent_id=intent_id,
            objective=objective,
            scope=scope,
        ),
        sender_principal_id=pid,
    )


def _conflicts_seen(received) -> List[Dict[str, Any]]:
    """Flatten CONFLICT_REPORT envelopes seen by anyone in this round."""
    seen: List[Dict[str, Any]] = []
    for envelopes in received.values():
        for env in envelopes:
            if env.get("message_type") == "CONFLICT_REPORT":
                seen.append(env["payload"])
    return seen


def _print_state(label, session, received):
    print(f"\n=== {label} ===")
    print("Active intents:")
    for intent in session.coordinator.intents.values():
        state = intent.state_machine.current_state.name
        print(f"  - {intent.intent_id} principal={intent.principal_id} "
              f"state={state} files={intent.scope.resources}")
    new_conflicts = _conflicts_seen(received)
    if new_conflicts:
        print("New CONFLICT_REPORTs this round:")
        # de-dup by conflict_id since both sides receive the same report
        seen_ids = set()
        for c in new_conflicts:
            cid = c.get("conflict_id")
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            print(f"  - {c.get('category')} "
                  f"{c.get('principal_a')} ↔ {c.get('principal_b')}")
    else:
        print("New CONFLICT_REPORTs this round: (none)")


async def main() -> int:
    session, participants, received = await _setup_session()

    # ─── Scenario 1: Dave's first attempt ──────────────────
    # Dave's claude -p subprocess announces an intent, then crashes
    # (content filter blocks the followup write). Pre-fix this would
    # leave the intent ACTIVE forever.
    await _announce(
        session, participants, received,
        pid="agent:user-3",
        intent_id="intent-dave-attempt-1",
        files=["notes_app/db.py"],
        objective="append 1000 lines of hello world",
    )
    _print_state("After Dave's first attempt (subprocess about to crash)",
                 session, received)
    assert (
        session.coordinator.intents["intent-dave-attempt-1"]
        .state_machine.current_state == IntentState.ACTIVE
    )
    # No conflicts yet.
    assert not _conflicts_seen(received), (
        "should be no conflicts after the first announce"
    )

    # The new relay cleanup endpoint would withdraw the orphan here.
    # We simulate the old buggy path FIRST (no cleanup) to show 2c.

    # ─── Scenario 2: Dave retries the same prompt (no cleanup) ────
    await _announce(
        session, participants, received,
        pid="agent:user-3",
        intent_id="intent-dave-attempt-2",
        files=["notes_app/db.py"],
        objective="append 1000 lines of hello world (retry)",
    )
    _print_state("After Dave's retry (without explicit cleanup)",
                 session, received)
    # Pre-fix: would emit a 'Dave ↔ Dave' CONFLICT_REPORT.
    # Post-fix: 2c auto-supersedes the orphan; 2a guarantees no self-conflict.
    self_conflicts = [
        c for c in _conflicts_seen(received)
        if c["principal_a"] == c["principal_b"]
    ]
    assert not self_conflicts, (
        f"REGRESSION: self-conflict detected: {self_conflicts}"
    )
    assert (
        session.coordinator.intents["intent-dave-attempt-1"]
        .state_machine.current_state == IntentState.WITHDRAWN
    ), "orphan intent should have been auto-superseded"
    assert (
        session.coordinator.intents["intent-dave-attempt-2"]
        .state_machine.current_state == IntentState.ACTIVE
    )

    # ─── Scenario 3: Alice arrives and announces same file ─────────
    await _announce(
        session, participants, received,
        pid="agent:user-1",
        intent_id="intent-alice-1",
        files=["notes_app/db.py"],
        objective="append 1000 lines of hello world",
    )
    _print_state("After Alice announces", session, received)
    # Should see exactly one Alice ↔ Dave conflict, referencing the LIVE
    # Dave intent (attempt-2), NOT the orphan (attempt-1).
    cross_conflicts = [
        c for c in _conflicts_seen(received)
        if {c["principal_a"], c["principal_b"]} == {
            "agent:user-1", "agent:user-3"
        }
    ]
    assert cross_conflicts, "expected one Alice ↔ Dave conflict"
    seen_ids = {c["conflict_id"] for c in cross_conflicts}
    assert len(seen_ids) == 1, (
        f"expected exactly one cross conflict, got {len(seen_ids)}"
    )
    payload = cross_conflicts[0]
    referenced = {payload["intent_a"], payload["intent_b"]}
    assert "intent-dave-attempt-1" not in referenced, (
        "fresh conflict must not reference the dead orphan"
    )
    assert referenced == {"intent-alice-1", "intent-dave-attempt-2"}

    # ─── Scenario 4: Bob's Claude calls check_overlap and yields ───
    # check_overlap is a passive read; it does NOT create an intent.
    # We only verify the registry stays clean (no Bob intent magically
    # appears, no Bob-related conflict).
    bob_intents = [
        i for i in session.coordinator.intents.values()
        if i.principal_id == "agent:user-2"
    ]
    assert not bob_intents, "Bob never announced; should have no intents"

    # ─── Scenario 5: relay cleanup endpoint mid-failure ────────────
    # This is the 2b path. Bob announces an intent, then his relay
    # subprocess fails. The relay calls /api/agent/intents/withdraw_all,
    # which we model below by running the exact loop the route uses.
    await _announce(
        session, participants, received,
        pid="agent:user-2",
        intent_id="intent-bob-stuck",
        files=["docs/foo.md"],
        objective="bob's failed write",
    )
    assert (
        session.coordinator.intents["intent-bob-stuck"]
        .state_machine.current_state == IntentState.ACTIVE
    )

    # Simulate /agent/intents/withdraw_all for principal agent:user-2.
    target_ids = [
        intent.intent_id
        for intent in session.coordinator.intents.values()
        if intent.principal_id == "agent:user-2"
        and intent.state_machine.current_state == IntentState.ACTIVE
    ]
    for intent_id in target_ids:
        envelope = participants["agent:user-2"].withdraw_intent(
            session_id=session.mpac_session_id,
            intent_id=intent_id,
            reason="claude_exit_1",
        )
        await process_envelope(
            session, envelope, sender_principal_id="agent:user-2",
        )
    assert (
        session.coordinator.intents["intent-bob-stuck"]
        .state_machine.current_state == IntentState.WITHDRAWN
    ), "relay cleanup should withdraw bob's stuck intent"
    print("\nScenario 5 — relay cleanup endpoint:")
    print(f"  withdrew {len(target_ids)} stuck intent(s) for agent:user-2")

    print("\n✅ All scenarios passed — fixes look correct end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
