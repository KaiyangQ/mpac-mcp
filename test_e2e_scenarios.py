#!/usr/bin/env python3
"""
Multi-scenario E2E test — 4 scenarios with long-lived connections.

Both agents stay connected throughout all scenarios, simulating real
collaborative sessions (not run-to-completion). This catches issues like
intent accumulation and stale-state-ref that single-task tests miss.

Scenarios:
  1. No-conflict: Alice → auth.py, Bob → api.py (concurrent)
  2. Conflict detection: both → auth.py (concurrent)
  3. Dependency: Alice → auth.py, then Bob builds on Alice's result
  4. Conflict + rebase: both → auth.py, both proceed (concurrent)

Usage:
    source test_site_A/.venv/bin/activate
    python test_e2e_scenarios.py

Requires: Anthropic API key in test_site_A/config.json
"""
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
    "test_site_A", ".venv", "lib", "python3.9", "site-packages"))

from mpac_protocol import MPACServer, MPACAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-20s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scenarios")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(SCRIPT_DIR, "test_site_A", "config.json")) as f:
    cfg = json.load(f)["anthropic"]

SESSION_ID = "scenario-test-001"
PORT = 8767  # Different port to avoid conflict with running coordinator
WORKSPACE = os.path.join(SCRIPT_DIR, "test_site_A", "workspace")


def banner(title: str):
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)
    print()


def print_workspace(server):
    print("  Workspace state:")
    for path, info in sorted(server.file_store.files.items()):
        print(f"    {path}: {info['state_ref']} ({len(info['content'])} bytes)")
    print()


def count_messages(transcript, msg_type: str) -> int:
    return sum(
        1 for t in transcript
        if t.get("envelope", {}).get("message_type") == msg_type
    )


def has_message_since(transcript, msg_type: str, since_index: int) -> bool:
    for t in transcript[since_index:]:
        if t.get("envelope", {}).get("message_type") == msg_type:
            return True
    return False


async def main():
    banner("MPAC Multi-Scenario E2E Test (Long-Connection)")
    results = {}

    # ── Setup ──
    print("[Setup] Starting coordinator...")
    server = MPACServer(
        session_id=SESSION_ID,
        host="0.0.0.0",
        port=PORT,
        workspace_dir=WORKSPACE,
    )
    ws_server, heartbeat_task = await server.run_background()
    await asyncio.sleep(0.5)

    print("[Setup] Creating agents...")
    alice = MPACAgent(
        name="Alice",
        api_key=cfg["api_key"],
        model=cfg.get("model", "claude-sonnet-4-6"),
        role_description="Security engineer — fixes auth bugs, token validation, timing attacks",
    )
    bob = MPACAgent(
        name="Bob",
        api_key=cfg["api_key"],
        model=cfg.get("model", "claude-sonnet-4-6"),
        role_description="API quality engineer — adds logging, input validation, error handling",
    )

    print("[Setup] Connecting agents...")
    await alice.connect(f"ws://localhost:{PORT}", SESSION_ID)
    await bob.connect(f"ws://localhost:{PORT}", SESSION_ID)
    await alice._do_hello()
    await bob._do_hello()
    await asyncio.sleep(0.5)

    print("[Setup] Ready. Starting scenarios.\n")

    # ══════════════════════════════════════════════════════════════
    #  Scenario 1: No-conflict collaboration
    # ══════════════════════════════════════════════════════════════
    banner("Scenario 1: No-Conflict (different files)")
    t_start = len(server.transcript)

    r_alice, r_bob = await asyncio.gather(
        alice.execute_task(
            "Fix the authentication security bugs in auth.py: "
            "add token expiry validation and fix the timing side-channel"
        ),
        bob.execute_task(
            "Add request logging and input validation to api.py"
        ),
    )

    has_conflict = has_message_since(server.transcript, "CONFLICT_REPORT", t_start)
    alice_ok = "auth.py" in r_alice["committed"]
    bob_ok = "api.py" in r_bob["committed"]
    passed = alice_ok and bob_ok and not has_conflict

    results["scenario_1"] = passed
    print(f"  Alice committed auth.py: {alice_ok}")
    print(f"  Bob committed api.py:    {bob_ok}")
    print(f"  Conflict detected:       {has_conflict}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    print_workspace(server)

    # ══════════════════════════════════════════════════════════════
    #  Scenario 2: Conflict detection (same file)
    # ══════════════════════════════════════════════════════════════
    banner("Scenario 2: Conflict Detection (same file)")
    t_start = len(server.transcript)

    r_alice, r_bob = await asyncio.gather(
        alice.execute_task("Refactor auth.py to use JWT library for token handling"),
        bob.execute_task("Add comprehensive error handling to auth.py"),
    )

    has_conflict = has_message_since(server.transcript, "CONFLICT_REPORT", t_start)
    either_committed = bool(r_alice["committed"]) or bool(r_bob["committed"])
    either_yielded = r_alice["yielded"] or r_bob["yielded"]
    # Pass if conflict was detected and at least one agent committed
    passed = has_conflict and either_committed

    results["scenario_2"] = passed
    print(f"  Conflict detected:       {has_conflict}")
    print(f"  Alice committed:         {r_alice['committed']}  yielded: {r_alice['yielded']}")
    print(f"  Bob committed:           {r_bob['committed']}  yielded: {r_bob['yielded']}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    print_workspace(server)

    # ══════════════════════════════════════════════════════════════
    #  Scenario 3: Dependency (sequential)
    # ══════════════════════════════════════════════════════════════
    banner("Scenario 3: Dependency (Alice first, then Bob)")
    t_start = len(server.transcript)

    # Record auth.py state before Alice
    auth_ref_before = server.file_store.files.get("auth.py", {}).get("state_ref", "?")

    r_alice = await alice.execute_task(
        "Add rate limiting to the authenticate function in auth.py"
    )
    alice_ok = "auth.py" in r_alice["committed"]

    # Record auth.py state after Alice, before Bob
    auth_ref_after_alice = server.file_store.files.get("auth.py", {}).get("state_ref", "?")

    r_bob = await bob.execute_task(
        "Based on the current auth.py, add logging to all functions"
    )
    bob_ok = "auth.py" in r_bob["committed"]

    # Bob's commit should be on top of Alice's version
    auth_ref_after_bob = server.file_store.files.get("auth.py", {}).get("state_ref", "?")
    chain_ok = (auth_ref_before != auth_ref_after_alice != auth_ref_after_bob)

    passed = alice_ok and bob_ok and chain_ok

    results["scenario_3"] = passed
    print(f"  Alice committed auth.py: {alice_ok}  ref: {auth_ref_after_alice}")
    print(f"  Bob committed auth.py:   {bob_ok}  ref: {auth_ref_after_bob}")
    print(f"  State chain valid:       {chain_ok} ({auth_ref_before[:16]} -> {auth_ref_after_alice[:16]} -> {auth_ref_after_bob[:16]})")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    print_workspace(server)

    # ══════════════════════════════════════════════════════════════
    #  Scenario 4: Conflict + Rebase
    # ══════════════════════════════════════════════════════════════
    banner("Scenario 4: Conflict + Rebase (both proceed)")
    t_start = len(server.transcript)

    r_alice, r_bob = await asyncio.gather(
        alice.execute_task("Add session management functions to auth.py"),
        bob.execute_task("Add password strength validation to auth.py"),
    )

    has_conflict = has_message_since(server.transcript, "CONFLICT_REPORT", t_start)
    has_stale = has_message_since(server.transcript, "PROTOCOL_ERROR", t_start)
    both_committed = "auth.py" in r_alice["committed"] and "auth.py" in r_bob["committed"]
    at_least_one = bool(r_alice["committed"]) or bool(r_bob["committed"])

    # Pass if conflict detected and at least one committed.
    # Ideal: both committed (rebase worked). Acceptable: one yielded.
    passed = has_conflict and at_least_one

    results["scenario_4"] = passed
    print(f"  Conflict detected:       {has_conflict}")
    print(f"  STALE_STATE_REF seen:    {has_stale}")
    print(f"  Alice committed:         {r_alice['committed']}  yielded: {r_alice['yielded']}")
    print(f"  Bob committed:           {r_bob['committed']}  yielded: {r_bob['yielded']}")
    print(f"  Both committed (rebase): {both_committed}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    print_workspace(server)

    # ══════════════════════════════════════════════════════════════
    #  Teardown
    # ══════════════════════════════════════════════════════════════
    banner("Summary")

    await alice._do_goodbye()
    await bob._do_goodbye()
    await alice.close()
    await bob.close()

    # Save transcript
    output_dir = os.path.join(SCRIPT_DIR, "test_output")
    os.makedirs(output_dir, exist_ok=True)
    server.file_store.save_to_directory(output_dir)
    server.save_transcript(os.path.join(output_dir, "scenarios_transcript.json"))

    # Message stats
    msg_types = {}
    for t in server.transcript:
        mt = t.get("envelope", {}).get("message_type", t.get("envelope", {}).get("type", "sideband"))
        msg_types[mt] = msg_types.get(mt, 0) + 1

    print("  Message counts:")
    for mt, count in sorted(msg_types.items()):
        print(f"    {mt}: {count}")
    print()

    # Final results
    all_passed = all(results.values())
    print("  Scenario results:")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"    {name}: {status}")
    print()
    print(f"  Total messages: {len(server.transcript)}")
    print(f"  Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    print()

    heartbeat_task.cancel()
    ws_server.close()
    await ws_server.wait_closed()

    return 0 if all_passed else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
