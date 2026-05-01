#!/usr/bin/env python3
"""Automated conflict-detection regression harness.

Runs the race-detection scenarios documented in
`docs/CONFLICT_TEST_SCENARIOS.md` (scenarios 7-9) **without** real Claude
in the loop — talks directly to the web-app's `/api/agent/*` HTTP surface
(the same surface mpac-mcp's relay_tools call) and observes the per-user
WS broadcasts a real browser would receive.

Phase 1 (this file) covers race detection only:
    7  cross-file dependency_breakage  → bob's announce response carries
                                          conflicts[*].their_impact_on_us
    8  same-file STALE_INTENT race lock → bob's announce returns HTTP 409
                                          + defer_intent + fast-resolve
    9  sequential same-file default-yield → check_overlap + defer_intent
                                            + fast-resolve

Phase 2 (TODO) extends to cases 1-6 (UI-driven scope_overlap +
dependency_breakage with real file edits). Phase 3 (TODO) wires the
exit code into CI.

Usage::

    # all 3 race-detection scenarios against prod
    .venv/bin/python scripts/conflict_test_harness.py --target prod

    # just scenario 8 (race lock) with verbose WS frame logging
    .venv/bin/python scripts/conflict_test_harness.py --target prod \\
        --scenario 8 --verbose

    # comma-separated subset
    .venv/bin/python scripts/conflict_test_harness.py --scenario 7,9

    # local target reads project_id from demo_driver creds file
    .venv/bin/python scripts/conflict_test_harness.py --target local

Requires httpx + websockets (already in the project's .venv).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import websockets


# ── Target configuration ──────────────────────────────────────────────

@dataclass
class Target:
    name: str
    base: str
    ws_base: str
    project_id: int | None  # None → resolve from creds file (local only)
    alice_email: str
    bob_email: str
    password: str


PROD_TARGET = Target(
    name="prod",
    base="https://mpac-web.duckdns.org",
    ws_base="wss://mpac-web.duckdns.org",
    project_id=1,
    alice_email="alice@mpac.test",
    bob_email="bob@mpac.test",
    password="mpac-test-2026",
)

LOCAL_TARGET = Target(
    name="local",
    base="http://127.0.0.1:8001",
    ws_base="ws://127.0.0.1:8001",
    project_id=None,  # resolved from demo_driver creds
    alice_email="alice@demo.local",
    bob_email="bob@demo.local",
    password="alice-pw-1",  # bob's pw is bob-pw-1; resolved from creds too
)


def resolve_local_target(creds_path: Path) -> Target:
    """Read /tmp/mpac_demo_creds.json (demo_driver setup output) for
    project_id + per-account passwords. Lets the harness ride on top of
    the same accounts demo_driver provisions.
    """
    if not creds_path.is_file():
        raise SystemExit(
            f"--target local needs {creds_path} (run "
            f"`scripts/demo_driver.py setup` first)."
        )
    creds = json.loads(creds_path.read_text())
    accts = creds["accounts"]
    return Target(
        name="local",
        base=creds["base"],
        ws_base=creds["ws_base"],
        project_id=creds["project_id"],
        alice_email=accts["alice"]["email"],
        bob_email=accts["bob"]["email"],
        password=accts["alice"]["password"],  # used only for alice; bob below
    )


# ── HTTP + WS helpers ─────────────────────────────────────────────────

@dataclass
class Account:
    label: str          # "alice" / "bob"
    email: str
    password: str
    user_token: str = ""
    user_id: int = 0
    agent_token: str = ""
    relay_ws: Any = None
    relay_drain_task: asyncio.Task | None = None

    @property
    def browser_principal(self) -> str:
        return f"user:{self.user_id}"

    @property
    def agent_principal(self) -> str:
        return f"agent:user-{self.user_id}"


async def open_fake_relay(ws_base: str, project_id: int, agent_token: str) -> tuple[Any, asyncio.Task]:
    """Open a /ws/relay/{pid} WS with the agent token + send the HELLO
    frame, then leave the connection open with a background drain task.

    The web-app's HTTP /api/agent/* endpoints all call _get_agent_conn()
    which checks `session.connections.get("agent:user-{id}")`. That map
    is populated at WS-relay connect time (register_and_hello in
    routes/ws_relay.py:231). Without the relay WS open the HTTP surface
    409s with "Agent not registered in session." — see commit log for
    the get_agent_conn invariant.

    The harness uses this to FAKE a relay being present without booting
    a real mpac-mcp + claude -p subprocess. Server-side this looks
    identical to a real relay that just hasn't been asked to chat yet.
    """
    url = f"{ws_base}/ws/relay/{project_id}"
    ws = await websockets.connect(
        url,
        additional_headers={"Authorization": f"Bearer {agent_token}"},
        max_size=2 ** 22,
    )
    # Server logs HELLO metadata + uses it as liveness; mirror what
    # mpac-mcp 0.2.5+ sends (see ws_relay.py:142-145).
    await ws.send(json.dumps({"type": "hello", "version": "harness-1.0"}))

    async def _drain() -> None:
        try:
            async for _ in ws:
                pass  # discard mpac_envelope frames; browser WS observes broadcasts
        except websockets.exceptions.ConnectionClosed:
            pass

    task = asyncio.create_task(_drain())
    return ws, task


class Observer:
    """A fake-browser WS connection that drains envelopes into a list.

    Mirrors what a real browser tab does: connect to /ws/session/{pid}
    with the user JWT, then sit there receiving INTENT_*, CONFLICT_*,
    and other broadcasts. The harness inspects the buffer to assert
    "this user's UI would have rendered X."
    """
    def __init__(self, label: str, verbose: bool = False) -> None:
        self.label = label
        self.verbose = verbose
        self.frames: list[dict] = []
        self._ws: Any = None
        self._task: asyncio.Task | None = None

    async def connect(self, ws_url: str) -> None:
        self._ws = await websockets.connect(
            ws_url,
            additional_headers={"Origin": ws_url.split("/ws/")[0].replace("wss://", "https://").replace("ws://", "http://")},
            max_size=2 ** 22,
        )
        self._task = asyncio.create_task(self._drain())
        # Wait briefly for SESSION_INFO so we know the WS is live before
        # the test starts firing announces. Without this the first
        # announce can race past the WS handshake.
        for _ in range(50):  # ~5s budget
            if any(f.get("message_type") == "SESSION_INFO" for f in self.frames):
                return
            await asyncio.sleep(0.1)
        raise SystemExit(f"[{self.label}] WS never sent SESSION_INFO")

    async def _drain(self) -> None:
        try:
            async for raw in self._ws:
                env = json.loads(raw)
                self.frames.append(env)
                if self.verbose:
                    self._log_frame(env)
        except websockets.exceptions.ConnectionClosed:
            pass

    def _log_frame(self, env: dict) -> None:
        mt = env.get("message_type", "?")
        sender = env.get("sender") or {}
        sender_id = (sender.get("display_name")
                     or sender.get("principal_id") or "?") if isinstance(sender, dict) else sender
        p = env.get("payload") or {}
        extra = ""
        if mt == "INTENT_ANNOUNCE":
            files = (p.get("scope") or {}).get("resources", [])
            extra = f"  files={files}"
        elif mt == "CONFLICT_REPORT":
            extra = (f"  category={p.get('category')!r} "
                     f"a={p.get('principal_a')} b={p.get('principal_b')}")
            if p.get("category") == "dependency_breakage":
                dep = p.get("dependency_detail") or {}
                extra += f" dep_ab={dep.get('ab')} dep_ba={dep.get('ba')}"
        elif mt == "INTENT_DEFERRED":
            extra = (f"  status={p.get('status', 'active')!r} "
                     f"observed={p.get('observed_intent_ids')}")
        elif mt == "INTENT_WITHDRAW":
            extra = f"  intent_id={p.get('intent_id')} reason={p.get('reason')!r}"
        print(f"  [{self.label:5s} ws] ← {mt}  from={sender_id}{extra}")

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()

    # ── frame queries used by assertions ──

    def of_type(self, mt: str) -> list[dict]:
        return [f for f in self.frames if f.get("message_type") == mt]

    def conflicts_of(self, category: str) -> list[dict]:
        return [
            f for f in self.of_type("CONFLICT_REPORT")
            if (f.get("payload") or {}).get("category") == category
        ]

    def deferreds_with_status(self, status: str) -> list[dict]:
        # 'active' broadcasts omit the status field per SPEC §15.5.1;
        # only resolved/expired carry it explicitly.
        out = []
        for f in self.of_type("INTENT_DEFERRED"):
            p = f.get("payload") or {}
            actual = p.get("status", "active")
            if actual == status:
                out.append(f)
        return out


class Client:
    """HTTP client that knows how to hit /api/agent/* on behalf of a
    given account. Keeps Alice + Bob accounts side-by-side so scenarios
    just say `await client.announce("bob", ...)`.
    """
    def __init__(self, target: Target) -> None:
        self.target = target
        self.http = httpx.AsyncClient(base_url=target.base, timeout=15.0)
        self.accounts: dict[str, Account] = {}

    async def login(self, label: str, email: str, password: str) -> Account:
        r = await self.http.post(
            "/api/login", json={"email": email, "password": password})
        r.raise_for_status()
        body = r.json()
        acct = Account(
            label=label, email=email, password=password,
            user_token=body["token"], user_id=body["user_id"],
        )
        # Mint agent token so HTTP /agent/* endpoints work.
        r = await self.http.post(
            f"/api/projects/{self.target.project_id}/agent-token",
            headers={"Authorization": f"Bearer {acct.user_token}"})
        r.raise_for_status()
        acct.agent_token = r.json()["token_value"]
        # Open the fake relay WS so /api/agent/* can find this principal
        # in the session connection map.
        acct.relay_ws, acct.relay_drain_task = await open_fake_relay(
            self.target.ws_base, self.target.project_id, acct.agent_token,
        )
        # Brief settle so coordinator's register_and_hello has finished.
        await asyncio.sleep(0.3)
        self.accounts[label] = acct
        return acct

    async def close(self) -> None:
        for acct in self.accounts.values():
            if acct.relay_ws is not None:
                try:
                    await acct.relay_ws.close()
                except Exception:
                    pass
            if acct.relay_drain_task is not None:
                try:
                    await asyncio.wait_for(acct.relay_drain_task, timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    acct.relay_drain_task.cancel()
        await self.http.aclose()

    def _agent_headers(self, label: str) -> dict:
        return {"Authorization": f"Bearer {self.accounts[label].agent_token}"}

    async def announce(
        self, label: str, files: list[str], objective: str,
        symbols: list[str] | None = None,
    ) -> tuple[int, dict]:
        """Returns (status_code, body). Does NOT raise on 4xx — scenarios
        need to inspect the 409 STALE_INTENT body."""
        body: dict[str, Any] = {
            "project_id": self.target.project_id,
            "files": files,
            "objective": objective,
        }
        if symbols is not None:
            body["symbols"] = symbols
        r = await self.http.post(
            "/api/agent/intents", json=body,
            headers=self._agent_headers(label),
        )
        try:
            payload = r.json()
        except json.JSONDecodeError:
            payload = {"raw": r.text}
        return r.status_code, payload

    async def withdraw(
        self, label: str, intent_id: str, reason: str = "test_done",
    ) -> dict:
        r = await self.http.request(
            "DELETE", "/api/agent/intents",
            json={
                "project_id": self.target.project_id,
                "intent_id": intent_id,
                "reason": reason,
            },
            headers=self._agent_headers(label),
        )
        r.raise_for_status()
        return r.json()

    async def withdraw_all(self, label: str, reason: str = "harness_cleanup") -> list[str]:
        r = await self.http.post(
            "/api/agent/intents/withdraw_all",
            json={"project_id": self.target.project_id, "reason": reason},
            headers=self._agent_headers(label),
        )
        r.raise_for_status()
        return r.json().get("withdrawn_intent_ids", [])

    async def defer(
        self, label: str, files: list[str],
        observed_intent_ids: list[str], reason: str = "yielded_to_active_editor",
    ) -> dict:
        r = await self.http.post(
            "/api/agent/intents/defer",
            json={
                "project_id": self.target.project_id,
                "files": files,
                "reason": reason,
                "observed_intent_ids": observed_intent_ids,
            },
            headers=self._agent_headers(label),
        )
        r.raise_for_status()
        return r.json()

    async def check_overlap(self, label: str, files: list[str]) -> list[dict]:
        r = await self.http.post(
            "/api/agent/overlap",
            json={"project_id": self.target.project_id, "files": files},
            headers=self._agent_headers(label),
        )
        r.raise_for_status()
        return r.json().get("overlaps", [])

    async def open_browser_ws(self, label: str, verbose: bool) -> Observer:
        url = (f"{self.target.ws_base}/ws/session/"
               f"{self.target.project_id}?token={self.accounts[label].user_token}")
        obs = Observer(label, verbose=verbose)
        await obs.connect(url)
        return obs


# ── Assertion helpers ─────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    name: str
    passed: int = 0
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


class Asserter:
    """Per-scenario assertion accumulator. Fail-soft: every assertion
    runs even when an earlier one failed, so a single run reports every
    broken invariant rather than stopping at the first."""

    def __init__(self, scenario_name: str) -> None:
        self.result = ScenarioResult(name=scenario_name)

    def check(self, cond: bool, label: str) -> None:
        if cond:
            self.result.passed += 1
            print(f"  ✓ {label}")
        else:
            self.result.failed.append(label)
            print(f"  ✗ {label}")

    def equals(self, actual: Any, expected: Any, label: str) -> None:
        ok = actual == expected
        if not ok:
            label = f"{label}  (got {actual!r}, want {expected!r})"
        self.check(ok, label)


# ── Scenarios ─────────────────────────────────────────────────────────

# Generous wait for WS broadcast propagation. Local is sub-50ms; prod
# adds TLS + duckdns hop, still typically under 300ms. 1.5s is slack.
BROADCAST_WAIT = 1.5
RACE_GAP = 0.6  # delay between alice's announce and bob's, kept short
                # so alice's intent is provably still ACTIVE when bob hits


async def scenario_7(client: Client, verbose: bool) -> ScenarioResult:
    """Cross-file dependency_breakage — bob's announce response carries
    same-tick conflicts (the ⚠️ warning surface introduced in v0.2.12).

    Alice announces on db.py with affects_symbols=[notes_app.db.save].
    Bob announces ~RACE_GAP later on api.py. Bob's announce response
    must include conflicts[*] with category=dependency_breakage and
    their_impact_on_us pointing at api.py + notes_app.db.save (the
    direction-fix from yesterday's `their_impact_on_us` commit).
    """
    a = Asserter("scenario 7 — cross-file dependency_breakage")
    print(f"\n[scenario 7] cross-file dep_breakage (alice db.py ↔ bob api.py)")

    alice_obs = await client.open_browser_ws("alice", verbose)
    bob_obs = await client.open_browser_ws("bob", verbose)
    alice_intent = bob_intent = None
    try:
        # Pre-clean leftovers from prior runs so we start with a quiet
        # session — race-lock state from a partially-cleaned earlier
        # scenario would mask the real outcome.
        await client.withdraw_all("alice")
        await client.withdraw_all("bob")
        # Drop SESSION_INFO + any cleanup-broadcast frames so the
        # buffers contain only what THIS scenario produces.
        alice_obs.frames.clear()
        bob_obs.frames.clear()

        # 1. Alice announces first; she should see no conflicts (alone).
        status, body = await client.announce(
            "alice", ["notes_app/db.py"],
            objective="harness 7: change save() return type",
            symbols=["notes_app.db.save"],
        )
        a.equals(status, 200, "alice announce returns 200")
        alice_intent = body.get("intent_id")
        a.check(bool(alice_intent), "alice announce body has intent_id")
        a.equals(body.get("conflicts", []), [], "alice announce conflicts empty (no peer yet)")

        await asyncio.sleep(RACE_GAP)

        # 2. Bob announces on api.py (which `from notes_app import db` →
        # uses db.save). Cross-file dependency_breakage must fire.
        status, body = await client.announce(
            "bob", ["notes_app/api.py"],
            objective="harness 7: add CORS header",
        )
        a.equals(status, 200, "bob announce returns 200 (no race lock — different file)")
        bob_intent = body.get("intent_id")
        a.check(bool(bob_intent), "bob announce body has intent_id")

        # The crown jewel for this scenario: same-tick conflicts surface.
        bob_conflicts = body.get("conflicts", [])
        a.check(len(bob_conflicts) >= 1,
                "bob announce response has same-tick conflicts (the ⚠️ surface)")
        if bob_conflicts:
            c = bob_conflicts[0]
            a.equals(c.get("category"), "dependency_breakage",
                     "bob's conflict category is dependency_breakage")
            a.equals(c.get("other_principal_id"),
                     client.accounts["alice"].agent_principal,
                     "bob's conflict points to alice as the other party")
            their_impact = c.get("their_impact_on_us") or []
            a.check(len(their_impact) >= 1,
                    "their_impact_on_us populated (the ab/ba direction fix)")
            if their_impact:
                hit = their_impact[0]
                a.equals(hit.get("file"), "notes_app/api.py",
                         "their_impact_on_us[0].file == api.py (bob's file)")
                syms = hit.get("symbols") or []
                a.check("notes_app.db.save" in syms,
                        "their_impact_on_us[0].symbols includes notes_app.db.save")

        await asyncio.sleep(BROADCAST_WAIT)

        # 3. Both browsers should have received CONFLICT_REPORT.
        for who, obs in (("alice", alice_obs), ("bob", bob_obs)):
            crs = obs.conflicts_of("dependency_breakage")
            a.check(len(crs) >= 1,
                    f"{who} browser WS received CONFLICT_REPORT(dependency_breakage)")

    finally:
        if alice_intent:
            try: await client.withdraw("alice", alice_intent)
            except Exception: pass
        if bob_intent:
            try: await client.withdraw("bob", bob_intent)
            except Exception: pass
        await alice_obs.close()
        await bob_obs.close()
    return a.result


async def scenario_8(client: Client, verbose: bool) -> ScenarioResult:
    """Same-file STALE_INTENT race lock + defer + fast-resolve.

    Alice announces on db.py; Bob's same-file announce ~RACE_GAP later
    must be hard-rejected (HTTP 409, error_code=STALE_INTENT) per SPEC
    §15.3.2. Bob then defers, observing alice's intent_id. When Alice
    withdraws, the coordinator emits INTENT_DEFERRED status=resolved
    (per §15.5.1 fast-resolve, condition (a)).
    """
    a = Asserter("scenario 8 — same-file STALE_INTENT race lock")
    print(f"\n[scenario 8] same-file race lock (both on db.py)")

    alice_obs = await client.open_browser_ws("alice", verbose)
    bob_obs = await client.open_browser_ws("bob", verbose)
    alice_intent = None
    try:
        await client.withdraw_all("alice")
        await client.withdraw_all("bob")
        alice_obs.frames.clear()
        bob_obs.frames.clear()

        # 1. Alice claims db.py first.
        status, body = await client.announce(
            "alice", ["notes_app/db.py"],
            objective="harness 8: refactor save (heavy)",
        )
        a.equals(status, 200, "alice announce returns 200")
        alice_intent = body.get("intent_id")
        a.check(bool(alice_intent), "alice has intent_id")

        await asyncio.sleep(RACE_GAP)

        # 2. Bob announces same file → must be 409 STALE_INTENT.
        status, body = await client.announce(
            "bob", ["notes_app/db.py"],
            objective="harness 8: bob also wants db.py (should be rejected)",
        )
        a.equals(status, 409, "bob announce returns 409 (race lock fired)")
        # FastAPI wraps detail dict under "detail" key.
        detail = body.get("detail") or {}
        a.equals(detail.get("error_code"), "STALE_INTENT",
                 "bob 409 body.detail.error_code == STALE_INTENT")
        a.check("notes_app/db.py" in (detail.get("files") or []),
                "bob 409 body.detail.files contains notes_app/db.py")
        a.check(alice_intent in (detail.get("description") or ""),
                "bob 409 description references alice's intent_id")
        # SPEC §15.3.2 — race-locked announce MUST NOT register and MUST
        # NOT generate CONFLICT_REPORT. Verify intent_id was NOT minted
        # by checking the rejected dict carries `intent_id_attempted`
        # (vs `intent_id` which only successful announces return).
        a.check("intent_id_attempted" in detail,
                "rejection carries intent_id_attempted (not registered)")

        # 3. Bob defers, observing alice's intent.
        defer_resp = await client.defer(
            "bob", ["notes_app/db.py"],
            observed_intent_ids=[alice_intent],
            reason="race_lock_yielded",
        )
        a.check(bool(defer_resp.get("deferral_id")),
                "bob defer returns deferral_id")
        a.equals(defer_resp.get("accepted"), True, "bob defer accepted")

        await asyncio.sleep(BROADCAST_WAIT)

        # 4. Both browsers should have seen INTENT_DEFERRED active.
        for who, obs in (("alice", alice_obs), ("bob", bob_obs)):
            actives = obs.deferreds_with_status("active")
            a.check(len(actives) >= 1,
                    f"{who} browser WS received INTENT_DEFERRED active (yield chip)")

        # SPEC §15.3.2 also forbids any CONFLICT_REPORT for the
        # race-locked collision.
        for who, obs in (("alice", alice_obs), ("bob", bob_obs)):
            scope_overlaps = obs.conflicts_of("scope_overlap")
            a.check(not scope_overlaps,
                    f"{who} browser WS got NO scope_overlap CONFLICT_REPORT (race lock pre-empts)")

        # 5. Alice withdraws → fast-resolve emits status=resolved.
        # Snapshot frame counts so we measure "after-withdraw" only.
        pre_withdraw_alice = len(alice_obs.frames)
        pre_withdraw_bob = len(bob_obs.frames)
        await client.withdraw("alice", alice_intent, reason="harness_done")
        alice_intent = None  # don't double-withdraw in finally
        await asyncio.sleep(BROADCAST_WAIT)

        for who, obs, baseline in (("alice", alice_obs, pre_withdraw_alice),
                                   ("bob", bob_obs, pre_withdraw_bob)):
            new_frames = obs.frames[baseline:]
            withdraws = [f for f in new_frames if f.get("message_type") == "INTENT_WITHDRAW"]
            resolved = [f for f in new_frames
                        if f.get("message_type") == "INTENT_DEFERRED"
                        and (f.get("payload") or {}).get("status") == "resolved"]
            a.check(len(withdraws) >= 1,
                    f"{who} browser WS got INTENT_WITHDRAW after alice withdrew")
            a.check(len(resolved) >= 1,
                    f"{who} browser WS got INTENT_DEFERRED status=resolved (fast-resolve)")

    finally:
        # Best-effort cleanup; withdraw_all is idempotent and Bob never
        # registered an intent in this scenario (was race-locked).
        try: await client.withdraw_all("alice")
        except Exception: pass
        try: await client.withdraw_all("bob")
        except Exception: pass
        await alice_obs.close()
        await bob_obs.close()
    return a.result


async def scenario_9(client: Client, verbose: bool) -> ScenarioResult:
    """Sequential same-file default-yield (simulates mpac-mcp 0.2.11
    default-yield prompt rule + mpac 0.2.7 fast-resolve, sans LLM).

    Alice announces on db.py. Bob queries check_overlap, observes alice
    on the same file, and chooses to defer rather than announce. The
    "defer rather than announce" decision is normally an LLM judgement
    call from the 0.2.11 prompt — this harness simulates the chosen
    branch. When alice withdraws, the deferral fast-resolves.
    """
    a = Asserter("scenario 9 — sequential same-file default-yield")
    print(f"\n[scenario 9] sequential same-file (default yield)")

    alice_obs = await client.open_browser_ws("alice", verbose)
    bob_obs = await client.open_browser_ws("bob", verbose)
    alice_intent = None
    try:
        await client.withdraw_all("alice")
        await client.withdraw_all("bob")
        alice_obs.frames.clear()
        bob_obs.frames.clear()

        # 1. Alice announces.
        status, body = await client.announce(
            "alice", ["notes_app/db.py"],
            objective="harness 9: add update/patch helpers",
        )
        a.equals(status, 200, "alice announce returns 200")
        alice_intent = body.get("intent_id")

        await asyncio.sleep(RACE_GAP)

        # 2. Bob check_overlap on the same file. Must surface alice's
        # intent with category=scope_overlap.
        overlaps = await client.check_overlap("bob", ["notes_app/db.py"])
        a.check(len(overlaps) >= 1, "bob check_overlap finds alice's intent")
        if overlaps:
            o = overlaps[0]
            a.equals(o.get("intent_id"), alice_intent,
                     "overlap entry carries alice's intent_id")
            a.equals(o.get("category"), "scope_overlap",
                     "overlap entry category == scope_overlap")
            a.equals(o.get("principal_id"),
                     client.accounts["alice"].agent_principal,
                     "overlap entry principal_id == alice's agent principal")

        # 3. Bob defers (the simulated default-yield branch).
        defer_resp = await client.defer(
            "bob", ["notes_app/db.py"],
            observed_intent_ids=[alice_intent],
            reason="default_yield_to_active_editor",
        )
        a.check(bool(defer_resp.get("deferral_id")), "bob defer returns deferral_id")

        await asyncio.sleep(BROADCAST_WAIT)

        for who, obs in (("alice", alice_obs), ("bob", bob_obs)):
            actives = obs.deferreds_with_status("active")
            a.check(len(actives) >= 1,
                    f"{who} browser WS received INTENT_DEFERRED active")

        # 4. Alice withdraws → fast-resolve.
        pre_alice = len(alice_obs.frames)
        pre_bob = len(bob_obs.frames)
        await client.withdraw("alice", alice_intent, reason="harness_done")
        alice_intent = None
        await asyncio.sleep(BROADCAST_WAIT)

        for who, obs, baseline in (("alice", alice_obs, pre_alice),
                                   ("bob", bob_obs, pre_bob)):
            new_frames = obs.frames[baseline:]
            resolved = [f for f in new_frames
                        if f.get("message_type") == "INTENT_DEFERRED"
                        and (f.get("payload") or {}).get("status") == "resolved"]
            a.check(len(resolved) >= 1,
                    f"{who} browser WS got INTENT_DEFERRED status=resolved (fast-resolve)")

    finally:
        try: await client.withdraw_all("alice")
        except Exception: pass
        try: await client.withdraw_all("bob")
        except Exception: pass
        await alice_obs.close()
        await bob_obs.close()
    return a.result


SCENARIOS = {
    "7": scenario_7,
    "8": scenario_8,
    "9": scenario_9,
}


# ── CLI ───────────────────────────────────────────────────────────────

def parse_scenarios(spec: str) -> list[str]:
    if spec == "all":
        return list(SCENARIOS.keys())
    out = []
    for token in spec.split(","):
        token = token.strip()
        if token not in SCENARIOS:
            raise SystemExit(f"unknown scenario {token!r} (valid: all, "
                             f"{','.join(SCENARIOS)})")
        out.append(token)
    return out


async def amain(args: argparse.Namespace) -> int:
    if args.target == "prod":
        target = PROD_TARGET
    else:
        target = resolve_local_target(Path(args.creds_file))

    if args.project_id is not None:
        target.project_id = args.project_id
    if target.project_id is None:
        raise SystemExit("Could not resolve project_id; pass --project-id")

    print(f"target: {target.name}  base={target.base}  project_id={target.project_id}")

    client = Client(target)
    try:
        await client.login("alice", target.alice_email, target.password)
        # Local target's bob has a separate password — load from creds.
        bob_pw = target.password
        if target.name == "local":
            creds = json.loads(Path(args.creds_file).read_text())
            bob_pw = creds["accounts"]["bob"]["password"]
        await client.login("bob", target.bob_email, bob_pw)
        print(f"logged in: alice user_id={client.accounts['alice'].user_id} "
              f"bob user_id={client.accounts['bob'].user_id}")

        results: list[ScenarioResult] = []
        for sid in parse_scenarios(args.scenario):
            t0 = time.monotonic()
            r = await SCENARIOS[sid](client, args.verbose)
            elapsed = time.monotonic() - t0
            print(f"[scenario {sid}] {'PASS' if r.ok else 'FAIL'} "
                  f"({r.passed}/{r.passed + len(r.failed)} asserts, {elapsed:.1f}s)")
            results.append(r)
    finally:
        await client.close()

    print("\n" + "=" * 64)
    pass_count = sum(1 for r in results if r.ok)
    print(f"summary: {pass_count}/{len(results)} scenarios passed")
    for r in results:
        if not r.ok:
            print(f"  ✗ {r.name}")
            for f in r.failed:
                print(f"      - {f}")
    print("=" * 64)
    return 0 if pass_count == len(results) else 1


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--target", choices=["prod", "local"], default="prod")
    p.add_argument("--scenario", default="all",
                   help="all, single id, or comma list (e.g. 7,8). "
                        f"Phase 1 supports: {','.join(SCENARIOS)}")
    p.add_argument("--project-id", type=int, default=None,
                   help="Override project_id (default: prod=1, local=from creds)")
    p.add_argument("--creds-file", default="/tmp/mpac_demo_creds.json",
                   help="demo_driver creds (used only for --target local)")
    p.add_argument("--verbose", action="store_true",
                   help="Log every WS frame as it arrives")
    args = p.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    sys.exit(main())
