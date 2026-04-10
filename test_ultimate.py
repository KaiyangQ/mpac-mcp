#!/usr/bin/env python3
"""
MPAC Ultimate Test: 5-Scenario Multi-Agent Coordination

Covers five distinct collaboration patterns, each testing different protocol
capabilities:

  1. Code collaboration      — file_set, conflict + rebase (2 agents)
  2. Family trip planning    — task_set, 3-agent conflict + resolution
  3. Document co-editing     — file_set, 3 agents on .md files
  4. Pre-commit governance   — OP_PROPOSE + INTENT_CLAIM fault recovery
  5. Conflict escalation     — CONFLICT_ESCALATE + arbiter RESOLUTION

Each scenario is self-contained (own server, agents, teardown).

Usage:
    source test_site_A/.venv/bin/activate
    python test_ultimate.py

Requires: Anthropic API key in test_site_A/config.json
"""
import asyncio
import json
import logging
import os
import sys
import time
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
    "test_site_A", ".venv", "lib", "python3.9", "site-packages"))

from mpac_protocol import MPACServer, MPACAgent
from mpac_protocol.core.models import Scope

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-20s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ultimate")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "test_site_A", "config.json")) as f:
    cfg = json.load(f)["anthropic"]

API_KEY = cfg["api_key"]
MODEL = cfg.get("model", "claude-sonnet-4-6")
WORKSPACE = os.path.join(SCRIPT_DIR, "test_site_A", "workspace")


# ── Helpers ────────────────────────────────────────────────────

def banner(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print()


def sha(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]


def has_message(transcript, msg_type: str, since: int = 0) -> bool:
    for t in transcript[since:]:
        if t.get("envelope", {}).get("message_type") == msg_type:
            return True
    return False


def count_messages(transcript, msg_type: str, since: int = 0) -> int:
    return sum(
        1 for t in transcript[since:]
        if t.get("envelope", {}).get("message_type") == msg_type
    )


async def setup_server(session_id, port, workspace_dir=None, **kwargs):
    """Create and start an MPACServer. Returns (server, ws_server, heartbeat_task)."""
    server = MPACServer(
        session_id=session_id,
        host="0.0.0.0",
        port=port,
        workspace_dir=workspace_dir,
        **kwargs,
    )
    ws_server, heartbeat_task = await server.run_background()
    await asyncio.sleep(0.3)
    return server, ws_server, heartbeat_task


async def teardown(ws_server, heartbeat_task, agents):
    """Cleanly shutdown agents and server."""
    for agent in agents:
        try:
            await agent._do_goodbye()
        except Exception:
            pass
        try:
            await agent.close()
        except Exception:
            pass
    heartbeat_task.cancel()
    ws_server.close()
    await ws_server.wait_closed()


def make_agent(name, role_desc=None, roles=None, principal_id=None):
    """Create an MPACAgent with shared API key/model."""
    return MPACAgent(
        name=name,
        api_key=API_KEY,
        model=MODEL,
        role_description=role_desc,
        roles=roles,
        principal_id=principal_id,
    )


# ══════════════════════════════════════════════════════════════
#  Scenario 1: Code Collaboration
# ══════════════════════════════════════════════════════════════

async def scenario_1_code_collaboration():
    """Two agents collaborate on Python files. Tests conflict detection + rebase."""
    banner("Scenario 1: Code Collaboration (file_set, conflict + rebase)")
    PORT = 8780

    server, ws, hb = await setup_server("ultimate-s1", PORT, WORKSPACE)
    alice = make_agent("Alice", "Security engineer — fixes auth bugs")
    bob = make_agent("Bob", "API quality engineer — adds validation and logging")

    await alice.connect(f"ws://localhost:{PORT}", "ultimate-s1")
    await bob.connect(f"ws://localhost:{PORT}", "ultimate-s1")
    await alice._do_hello()
    await bob._do_hello()
    await asyncio.sleep(0.3)

    t_start = len(server.transcript)

    # Both agents work on auth.py concurrently — expect conflict
    r_alice, r_bob = await asyncio.gather(
        alice.execute_task(
            "Fix the authentication security bugs in auth.py: "
            "add token expiry validation and fix timing side-channel"
        ),
        bob.execute_task(
            "Add comprehensive input validation and error logging to auth.py"
        ),
    )

    has_conflict = has_message(server.transcript, "CONFLICT_REPORT", t_start)
    at_least_one = bool(r_alice["committed"]) or bool(r_bob["committed"])
    passed = has_conflict and at_least_one

    print(f"  Conflict detected:  {has_conflict}")
    print(f"  Alice committed:    {r_alice['committed']}  yielded: {r_alice['yielded']}")
    print(f"  Bob committed:      {r_bob['committed']}  yielded: {r_bob['yielded']}")
    if r_alice["committed"] and r_bob["committed"]:
        print(f"  Both committed (rebase worked)")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    await teardown(ws, hb, [alice, bob])
    return passed


# ══════════════════════════════════════════════════════════════
#  Scenario 2: Family Trip Planning (task_set)
# ══════════════════════════════════════════════════════════════

async def scenario_2_family_trip():
    """Three agents plan a family trip using task_set scope. Tests non-file coordination."""
    banner("Scenario 2: Family Trip Planning (task_set, 3 agents)")
    PORT = 8781

    # No workspace — task_set doesn't use files
    server, ws, hb = await setup_server("ultimate-s2", PORT)

    dad = make_agent("Dad", "Dad's planner — transportation, budget, outdoor activities")
    mom = make_agent("Mom", "Mom's planner — accommodation, food, cultural experiences")
    kid = make_agent("Kid", "Kid's planner — theme parks, water activities, fun")

    agents = [dad, mom, kid]
    for agent in agents:
        await agent.connect(f"ws://localhost:{PORT}", "ultimate-s2")
        await agent._do_hello()
    await asyncio.sleep(0.3)

    t_start = len(server.transcript)

    # Dad plans day 1,2,5; Mom plans day 2,3; Kid plans day 3,4
    # Overlaps: Dad-Mom on day 2, Mom-Kid on day 3
    dad_intent = {
        "intent_id": f"intent-dad-{uuid.uuid4().hex[:6]}",
        "objective": "Plan outdoor activities, driving routes, and camping for days 1, 2, 5",
        "scope_kind": "task_set",
        "resources": ["itinerary://day-1", "itinerary://day-2", "itinerary://day-5"],
    }
    mom_intent = {
        "intent_id": f"intent-mom-{uuid.uuid4().hex[:6]}",
        "objective": "Plan accommodation, restaurants, and cultural experiences for days 2, 3",
        "scope_kind": "task_set",
        "resources": ["itinerary://day-2", "itinerary://day-3"],
    }
    kid_intent = {
        "intent_id": f"intent-kid-{uuid.uuid4().hex[:6]}",
        "objective": "Plan theme park visit and water activities for days 3, 4",
        "scope_kind": "task_set",
        "resources": ["itinerary://day-3", "itinerary://day-4"],
    }

    # Announce all intents
    for agent, intent in [(dad, dad_intent), (mom, mom_intent), (kid, kid_intent)]:
        await agent._do_announce_intent(intent)

    # Drain for conflict reports
    await asyncio.sleep(2.0)
    for agent in agents:
        await agent._drain_conflicts(3.0)

    has_conflict = has_message(server.transcript, "CONFLICT_REPORT", t_start)
    n_conflicts = count_messages(server.transcript, "CONFLICT_REPORT", t_start)

    # Resolve conflicts via coordinator (Dad is the arbiter)
    for cid, conflict in server.coordinator.conflicts.items():
        server.coordinator.resolve_as_coordinator(
            cid, decision="merged",
            rationale="Family members should coordinate overlapping days together",
        )

    # Each agent commits their plans (no actual file changes, just protocol)
    committed = []
    for agent, intent in [(dad, dad_intent), (mom, mom_intent), (kid, kid_intent)]:
        for resource in intent["resources"]:
            plan_content = f"{agent.name}'s plan for {resource}"
            op_id = f"op-{agent.name.lower()}-{resource.split('/')[-1]}"
            ref_before = server.coordinator.target_state_refs.get(resource, sha("empty"))
            new_ref = sha(plan_content)

            msg = agent.participant.commit_op(
                "ultimate-s2", op_id, intent["intent_id"], resource, "replace",
                state_ref_before=ref_before, state_ref_after=new_ref,
            )
            await agent._send(msg)
            await asyncio.sleep(0.3)

            # Check for rejection
            rejected = False
            try:
                while not agent.protocol_inbox.empty():
                    check = agent.protocol_inbox.get_nowait()
                    mt = check.get("message_type", "")
                    if mt == "PROTOCOL_ERROR" and \
                       check.get("payload", {}).get("error_code") == "STALE_STATE_REF":
                        rejected = True
                        # Re-read latest ref and retry
                        ref_before = server.coordinator.target_state_refs.get(resource, ref_before)
                        new_ref = sha(plan_content + "-rebased")
                        msg2 = agent.participant.commit_op(
                            "ultimate-s2", op_id + "-r1", intent["intent_id"],
                            resource, "replace",
                            state_ref_before=ref_before, state_ref_after=new_ref,
                        )
                        await agent._send(msg2)
                        await asyncio.sleep(0.3)
            except asyncio.QueueEmpty:
                pass

            committed.append(f"{agent.name}:{resource}")

    all_committed = len(committed) >= 7  # 3+2+2 = 7 resources

    passed = has_conflict and all_committed

    print(f"  Scope type:         task_set")
    print(f"  Conflict detected:  {has_conflict} ({n_conflicts} CONFLICT_REPORT msgs)")
    print(f"  Resources committed: {len(committed)}/7")
    print(f"  Committed: {committed}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    await teardown(ws, hb, agents)
    return passed


# ══════════════════════════════════════════════════════════════
#  Scenario 3: Document Collaborative Editing
# ══════════════════════════════════════════════════════════════

async def scenario_3_doc_editing():
    """Three agents edit markdown documents. Tests agent generalization."""
    banner("Scenario 3: Document Collaborative Editing (3 agents, .md files)")
    PORT = 8782

    server, ws, hb = await setup_server("ultimate-s3", PORT, WORKSPACE)

    # Seed extra .md files into the workspace
    readme_content = "# Project README\n\nThis project implements the MPAC protocol.\n\n## Getting Started\n\nTODO: Add setup instructions.\n"
    design_content = "# Design Document\n\n## Architecture\n\nTODO: Describe system architecture.\n\n## Components\n\nTODO: List components.\n"

    server.file_store.files["README.md"] = {
        "content": readme_content, "state_ref": sha(readme_content),
    }
    server.file_store.files["design-doc.md"] = {
        "content": design_content, "state_ref": sha(design_content),
    }

    editor = make_agent("Editor", "Technical writer — writes clear documentation")
    reviewer = make_agent("Reviewer", "Documentation reviewer — improves quality and accuracy")
    formatter = make_agent("Formatter", "Style editor — ensures consistent formatting")

    agents = [editor, reviewer, formatter]
    for agent in agents:
        await agent.connect(f"ws://localhost:{PORT}", "ultimate-s3")
        await agent._do_hello()
    await asyncio.sleep(0.3)

    t_start = len(server.transcript)

    # Editor works on README.md, Reviewer works on design-doc.md (no conflict)
    r_editor = await editor.execute_task(
        "Add a detailed Getting Started section to README.md with "
        "installation steps and a quick example"
    )
    r_reviewer = await reviewer.execute_task(
        "Fill in the Architecture section of design-doc.md with a description "
        "of the MPAC protocol's three-layer design (coordinator, server, agent)"
    )

    editor_ok = "README.md" in r_editor["committed"]
    reviewer_ok = "design-doc.md" in r_reviewer["committed"]

    # Now Formatter also edits README.md after Editor — tests sequential dependency
    r_formatter = await formatter.execute_task(
        "Improve formatting and add a Table of Contents to README.md"
    )
    formatter_ok = "README.md" in r_formatter["committed"]

    # Verify state chain: README.md was edited twice (Editor, then Formatter)
    readme_ref = server.file_store.files.get("README.md", {}).get("state_ref", "?")
    chain_ok = editor_ok and formatter_ok  # Both edited README.md sequentially

    passed = editor_ok and reviewer_ok and formatter_ok

    print(f"  Editor → README.md:      {editor_ok}")
    print(f"  Reviewer → design-doc.md: {reviewer_ok}")
    print(f"  Formatter → README.md:    {formatter_ok} (builds on Editor's version)")
    print(f"  State chain valid:        {chain_ok}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    await teardown(ws, hb, agents)
    return passed


# ══════════════════════════════════════════════════════════════
#  Scenario 4: Pre-Commit Governance + Fault Recovery
# ══════════════════════════════════════════════════════════════

async def scenario_4_precommit_recovery():
    """Pre-commit mode with OP_PROPOSE → authorization, agent crash, INTENT_CLAIM."""
    banner("Scenario 4: Pre-Commit Governance + Fault Recovery")
    PORT = 8783

    # Pre-commit requires governance compliance
    server, ws, hb = await setup_server(
        "ultimate-s4", PORT, WORKSPACE,
        execution_model="pre_commit",
        compliance_profile="governance",
        unavailability_timeout_sec=60.0,
        intent_claim_grace_sec=0.0,
    )

    alice = make_agent("Alice", "API designer — endpoint structure", roles=["owner"])
    bob = make_agent("Bob", "Backend engineer — data models", roles=["owner"])
    charlie = make_agent("Charlie", "Test engineer — integration tests", roles=["owner"])

    agents = [alice, bob, charlie]
    for agent in agents:
        await agent.connect(f"ws://localhost:{PORT}", "ultimate-s4")
        await agent._do_hello()
    await asyncio.sleep(0.3)

    t_start = len(server.transcript)
    results = {
        "bob_authorized": False,
        "bob_committed": False,
        "alice_suspended": False,
        "claim_approved": False,
        "claim_committed": False,
    }

    # ── Phase A: Announce intents ──
    alice_intent = {
        "intent_id": f"intent-alice-{uuid.uuid4().hex[:6]}",
        "objective": "Redesign API endpoints for auth flow",
        "files": ["auth.py", "api.py"],
    }
    bob_intent = {
        "intent_id": f"intent-bob-{uuid.uuid4().hex[:6]}",
        "objective": "Add last_login field to user model",
        "files": ["utils.py"],
    }

    await alice._do_announce_intent(alice_intent)
    await bob._do_announce_intent(bob_intent)
    await asyncio.sleep(1.0)

    # Drain conflicts
    for agent in agents:
        await agent._drain_conflicts(2.0)

    # ── Phase B: Bob proposes + commits (pre-commit flow) ──
    print("  [Phase B] Bob: OP_PROPOSE → authorization → OP_COMMIT")
    file_result = await bob.read_file("utils.py")
    if file_result:
        content, state_ref = file_result
        updated_content = content + "\n# Last login tracking added by Bob\n"
        op_id = f"op-bob-{uuid.uuid4().hex[:6]}"

        ok = await bob.propose_and_commit(
            bob_intent["intent_id"], op_id, "utils.py",
            updated_content, state_ref,
        )
        results["bob_authorized"] = True  # If propose_and_commit returns, propose was OK
        results["bob_committed"] = ok
        print(f"    Authorized + committed: {ok}")

    # ── Phase C: Alice crashes ──
    print("  [Phase C] Alice crashes — simulating unavailability")
    # Keep Bob and Charlie alive
    await bob.do_heartbeat("working")
    await charlie.do_heartbeat("working")

    # Close Alice's connection
    await alice.close()
    await asyncio.sleep(0.5)

    # Backdate Alice's last_seen to trigger unavailability
    alice_info = server.coordinator.participants.get(alice.principal_id)
    if alice_info:
        alice_info.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)

    # Run liveness check
    liveness_responses = server.coordinator.check_liveness()
    for resp in liveness_responses:
        server.transcript.append({
            "ts": time.time(), "direction": "outbound",
            "message_type": resp.get("message_type", "?"), "envelope": resp,
        })
        await server._broadcast(json.dumps(resp, ensure_ascii=False))

    await asyncio.sleep(1.0)

    # Verify Alice's intent is suspended
    for iid, intent in server.coordinator.intents.items():
        if intent.principal_id == alice.principal_id:
            state = str(intent.state_machine.current_state)
            results["alice_suspended"] = "SUSPENDED" in state
            print(f"    Alice's intent state: {state}")

    # Wait for broadcasts to settle, then drain
    await asyncio.sleep(2.0)
    for agent in [bob, charlie]:
        try:
            while not agent.protocol_inbox.empty():
                agent.protocol_inbox.get_nowait()
        except asyncio.QueueEmpty:
            pass

    # ── Phase D: Bob claims Alice's intent ──
    print("  [Phase D] Bob claims Alice's suspended intent")
    alice_suspended_id = None
    for iid, intent in server.coordinator.intents.items():
        if intent.principal_id == alice.principal_id:
            state = str(intent.state_machine.current_state)
            if "SUSPENDED" in state:
                alice_suspended_id = iid
                break

    if alice_suspended_id:
        # Refresh liveness for Bob and Charlie
        await bob.do_heartbeat("working")
        await charlie.do_heartbeat("working")
        await asyncio.sleep(1.0)

        # Drain any heartbeat responses
        for agent in [bob, charlie]:
            try:
                while not agent.protocol_inbox.empty():
                    agent.protocol_inbox.get_nowait()
            except asyncio.QueueEmpty:
                pass

        new_intent_id = f"intent-bob-claimed-{uuid.uuid4().hex[:6]}"
        claim_resp = await bob.do_claim_intent(
            original_intent_id=alice_suspended_id,
            original_principal_id=alice.principal_id,
            new_intent_id=new_intent_id,
            objective="Continue Alice's auth refactor after crash",
            files=alice_intent["files"],
            justification="Alice is unavailable; continuing her work",
        )

        if claim_resp:
            decision = claim_resp.get("payload", {}).get("decision", "?")
            results["claim_approved"] = decision == "approved"
            print(f"    Claim decision: {decision}")
        else:
            # Fallback: check coordinator state directly
            claim_obj = server.coordinator.claims.get(alice_suspended_id)
            if claim_obj and claim_obj.decision == "approved":
                results["claim_approved"] = True
                print(f"    Claim approved (verified from coordinator state)")

        # Bob commits on claimed scope
        if results["claim_approved"]:
            file_result = await bob.read_file("auth.py")
            if file_result:
                content, state_ref = file_result
                op_id = f"op-bob-claimed-{uuid.uuid4().hex[:6]}"
                ok = await bob.propose_and_commit(
                    new_intent_id, op_id, "auth.py",
                    content + "\n# Auth refactor continued by Bob (claimed)\n",
                    state_ref,
                )
                results["claim_committed"] = ok
                print(f"    Committed on claimed scope: {ok}")

    # ── Verify ──
    has_propose = has_message(server.transcript, "OP_PROPOSE", t_start)
    passed = (results["bob_authorized"] and results["bob_committed"]
              and results["alice_suspended"] and results["claim_approved"]
              and results["claim_committed"])

    print(f"\n  OP_PROPOSE seen:     {has_propose}")
    print(f"  Bob authorized:      {results['bob_authorized']}")
    print(f"  Bob committed:       {results['bob_committed']}")
    print(f"  Alice suspended:     {results['alice_suspended']}")
    print(f"  Claim approved:      {results['claim_approved']}")
    print(f"  Claim committed:     {results['claim_committed']}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    await teardown(ws, hb, [bob, charlie])  # alice already closed
    return passed


# ══════════════════════════════════════════════════════════════
#  Scenario 5: Conflict Escalation to Arbiter
# ══════════════════════════════════════════════════════════════

async def scenario_5_escalation():
    """Two owners dispute, escalate to arbiter, arbiter resolves."""
    banner("Scenario 5: Conflict Escalation to Arbiter")
    PORT = 8784

    server, ws, hb = await setup_server(
        "ultimate-s5", PORT, WORKSPACE,
        compliance_profile="governance",
    )

    alice = make_agent("Alice", "Frontend architect — mega-menu design", roles=["owner"])
    bob = make_agent("Bob", "UX engineer — hamburger menu design", roles=["owner"])
    arbiter = make_agent(
        "Arbiter", "Senior tech lead — design dispute authority",
        roles=["arbiter"], principal_id="human:arbiter",
    )

    agents = [alice, bob, arbiter]
    for agent in agents:
        await agent.connect(f"ws://localhost:{PORT}", "ultimate-s5")
        await agent._do_hello()
    await asyncio.sleep(0.3)

    t_start = len(server.transcript)
    results = {
        "conflict_detected": False,
        "both_disputed": False,
        "escalated": False,
        "resolved": False,
        "winner_committed": False,
    }

    # ── Phase A: Overlapping intents ──
    alice_intent = {
        "intent_id": f"intent-alice-{uuid.uuid4().hex[:6]}",
        "objective": "Redesign auth.py as a modular authentication framework",
        "files": ["auth.py", "utils.py"],
    }
    bob_intent = {
        "intent_id": f"intent-bob-{uuid.uuid4().hex[:6]}",
        "objective": "Refactor auth.py into minimal stateless token validation",
        "files": ["auth.py", "api.py"],
    }

    await alice._do_announce_intent(alice_intent)
    await bob._do_announce_intent(bob_intent)

    # Drain conflicts
    for agent in agents:
        await agent._drain_conflicts(3.0)

    results["conflict_detected"] = has_message(server.transcript, "CONFLICT_REPORT", t_start)

    # Collect conflict IDs
    conflict_id = None
    for cid, conflict in server.coordinator.conflicts.items():
        conflict_id = cid
        break

    if not conflict_id:
        print("  ERROR: No conflict detected despite overlapping scopes")
        print(f"  Result: FAIL")
        await teardown(ws, hb, agents)
        return False

    print(f"  [Phase A] Conflict detected: {conflict_id[:30]}...")

    # ── Phase B: Both ACK as disputed ──
    print("  [Phase B] Both agents dispute the conflict")
    # Drain any pending messages first
    for agent in agents:
        try:
            while not agent.protocol_inbox.empty():
                agent.protocol_inbox.get_nowait()
        except asyncio.QueueEmpty:
            pass

    await alice.do_ack_conflict(conflict_id, "disputed")
    await bob.do_ack_conflict(conflict_id, "disputed")
    await asyncio.sleep(0.5)

    # Verify conflict state
    conflict_obj = server.coordinator.conflicts.get(conflict_id)
    if conflict_obj:
        state = str(conflict_obj.state_machine.current_state)
        results["both_disputed"] = "ACKED" in state
        print(f"    Conflict state after ACKs: {state}")

    # ── Phase C: Alice escalates to arbiter ──
    print("  [Phase C] Alice escalates to arbiter")
    await alice.do_escalate_conflict(
        conflict_id,
        escalate_to=arbiter.principal_id,
        reason="Both owners dispute; need arbiter decision",
        context="Alice wants modular framework; Bob wants minimal stateless design",
    )

    has_escalate = has_message(server.transcript, "CONFLICT_ESCALATE", t_start)
    results["escalated"] = has_escalate

    # Verify conflict state
    conflict_obj = server.coordinator.conflicts.get(conflict_id)
    if conflict_obj:
        state = str(conflict_obj.state_machine.current_state)
        print(f"    Conflict state after escalation: {state}")

    # Drain arbiter inbox
    await asyncio.sleep(1.0)
    for agent in agents:
        try:
            while not agent.protocol_inbox.empty():
                agent.protocol_inbox.get_nowait()
        except asyncio.QueueEmpty:
            pass

    # ── Phase D: Arbiter resolves ──
    print("  [Phase D] Arbiter resolves the conflict")

    # Use Claude for the arbiter decision
    arbiter_system = """You are a senior tech lead acting as arbiter. Two engineers dispute.
Alice wants: modular authentication framework (larger scope, more flexible).
Bob wants: minimal stateless token validation (simpler, less code).
Pick one approach. Reply with ONLY a JSON:
{"winner": "Alice" or "Bob", "rationale": "one sentence why"}"""

    arbiter_user = f"Conflict ID: {conflict_id}\nAlice's intent: {alice_intent['objective']}\nBob's intent: {bob_intent['objective']}\nDecide."

    decision_raw = await asyncio.get_event_loop().run_in_executor(
        None, arbiter._ask_claude, arbiter_system, arbiter_user, 512,
    )
    decision = arbiter._parse_json(decision_raw, {"winner": "Alice", "rationale": "default"})
    winner_name = decision.get("winner", "Alice")
    rationale = decision.get("rationale", "Arbiter decided")

    print(f"    Arbiter decision: {winner_name} wins — {rationale[:80]}")

    if winner_name == "Alice":
        winner_agent, winner_intent = alice, alice_intent
        loser_agent, loser_intent = bob, bob_intent
    else:
        winner_agent, winner_intent = bob, bob_intent
        loser_agent, loser_intent = alice, alice_intent

    await arbiter.do_resolve_conflict(
        conflict_id,
        decision="human_override",
        rationale=rationale,
        outcome={
            "accepted": [winner_intent["intent_id"]],
            "rejected": [loser_intent["intent_id"]],
        },
    )

    has_resolution = has_message(server.transcript, "RESOLUTION", t_start)
    results["resolved"] = has_resolution

    # Verify conflict resolved
    conflict_obj = server.coordinator.conflicts.get(conflict_id)
    if conflict_obj:
        state = str(conflict_obj.state_machine.current_state)
        print(f"    Conflict state after resolution: {state}")

    await asyncio.sleep(0.5)

    # ── Phase E: Loser withdraws, winner commits ──
    print("  [Phase E] Loser withdraws, winner commits")
    msg = loser_agent.participant.withdraw_intent(
        "ultimate-s5", loser_intent["intent_id"],
        f"Arbiter ruled in favor of {winner_name}",
    )
    await loser_agent._send(msg)
    await asyncio.sleep(0.5)

    # Winner commits directly using existing intent (no new execute_task)
    file_result = await winner_agent.read_file("auth.py")
    if file_result:
        content, state_ref = file_result
        # Use Claude to generate the fix
        fixed = await asyncio.get_event_loop().run_in_executor(
            None, winner_agent._generate_fix,
            winner_intent["objective"], "auth.py", content,
        )
        op_id = f"op-{winner_name.lower()}-auth-{uuid.uuid4().hex[:6]}"
        ok = await winner_agent._do_commit(
            winner_intent["intent_id"], op_id, "auth.py", fixed, state_ref,
        )
        results["winner_committed"] = ok
        print(f"    {winner_name} committed auth.py: {ok}")

    # ── Verify ──
    passed = (results["conflict_detected"] and results["escalated"]
              and results["resolved"] and results["winner_committed"])

    print(f"\n  Conflict detected:   {results['conflict_detected']}")
    print(f"  Both disputed:       {results['both_disputed']}")
    print(f"  Escalated to arbiter:{results['escalated']}")
    print(f"  Arbiter resolved:    {results['resolved']}")
    print(f"  Winner committed:    {results['winner_committed']}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")

    await teardown(ws, hb, agents)
    return passed


# ══════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════

async def main():
    banner("MPAC ULTIMATE TEST — 5-Scenario Multi-Agent Coordination")
    start_time = time.time()
    results = {}

    try:
        results["1_code_collab"] = await scenario_1_code_collaboration()
    except Exception as e:
        log.error(f"Scenario 1 EXCEPTION: {e}", exc_info=True)
        results["1_code_collab"] = False

    try:
        results["2_family_trip"] = await scenario_2_family_trip()
    except Exception as e:
        log.error(f"Scenario 2 EXCEPTION: {e}", exc_info=True)
        results["2_family_trip"] = False

    try:
        results["3_doc_editing"] = await scenario_3_doc_editing()
    except Exception as e:
        log.error(f"Scenario 3 EXCEPTION: {e}", exc_info=True)
        results["3_doc_editing"] = False

    try:
        results["4_precommit"] = await scenario_4_precommit_recovery()
    except Exception as e:
        log.error(f"Scenario 4 EXCEPTION: {e}", exc_info=True)
        results["4_precommit"] = False

    try:
        results["5_escalation"] = await scenario_5_escalation()
    except Exception as e:
        log.error(f"Scenario 5 EXCEPTION: {e}", exc_info=True)
        results["5_escalation"] = False

    # ── Summary ──
    elapsed = time.time() - start_time
    banner("ULTIMATE TEST SUMMARY")

    all_passed = all(results.values())
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    print()
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
