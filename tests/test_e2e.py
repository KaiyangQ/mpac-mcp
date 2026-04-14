#!/usr/bin/env python3
"""
End-to-end test: simulates Site A + Site B in one process.

Both agents use the pip-installed mpac_protocol package,
communicate only through WebSocket — just like two separate machines.
"""
import asyncio
import json
import logging
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

# Add examples/two_machine_demo/host's venv to path (both have the same package)
sys.path.insert(0, os.path.join(REPO_ROOT,
    "examples/two_machine_demo/host", ".venv", "lib", "python3.9", "site-packages"))

from mpac_protocol import MPACServer, MPACAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-20s] %(message)s",
    datefmt="%H:%M:%S",
)

with open(os.path.join(REPO_ROOT, "examples/two_machine_demo/host", "config.json")) as f:
    cfg = json.load(f)["anthropic"]

SESSION_ID = "e2e-test-001"
PORT = 8766
WORKSPACE = os.path.join(REPO_ROOT, "examples/two_machine_demo/host", "workspace")


async def main():
    print("=" * 65)
    print("  MPAC E2E Test: Two agents from two 'sites' via pip package")
    print("=" * 65)
    print()

    # ── 1. Start coordinator (Site A hosts it) ──
    print("[1/7] Starting coordinator with workspace...")
    server = MPACServer(
        session_id=SESSION_ID,
        host="0.0.0.0",
        port=PORT,
        workspace_dir=WORKSPACE,
    )
    ws_server, heartbeat_task = await server.run_background()
    await asyncio.sleep(0.5)

    # ── 2. Create agents (simulate two different machines) ──
    print("[2/7] Creating agents...")
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

    # ── 3. Connect both (through WebSocket, like remote machines) ──
    print("[3/7] Connecting agents to coordinator...")
    await alice.connect(f"ws://localhost:{PORT}", SESSION_ID)
    await bob.connect(f"ws://localhost:{PORT}", SESSION_ID)

    # ── 4. Run tasks concurrently ──
    print("[4/7] Running tasks concurrently...")
    print()
    await asyncio.gather(
        alice.run_task(
            "Fix the authentication security bugs in auth.py: "
            "add token expiry validation and fix the timing side-channel"
        ),
        bob.run_task(
            "Add request logging and input validation to api.py"
        ),
    )

    # ── 5. Close connections ──
    print()
    print("[5/7] Closing connections...")
    await alice.close()
    await bob.close()

    # ── 6. Print final workspace state ──
    print()
    print("[6/7] Final workspace state:")
    print("-" * 50)
    for path, info in sorted(server.file_store.files.items()):
        print(f"  {path}: {info['state_ref']} ({len(info['content'])} bytes)")
    print()

    # Print modified file contents
    for path, info in sorted(server.file_store.files.items()):
        print(f"=== {path} (final) ===")
        # Show first 30 lines
        lines = info["content"].split("\n")
        for i, line in enumerate(lines[:30]):
            print(f"  {i+1:3d} | {line}")
        if len(lines) > 30:
            print(f"  ... ({len(lines) - 30} more lines)")
        print()

    # ── 7. Save results ──
    output_dir = os.path.join(REPO_ROOT, "test_output")
    os.makedirs(output_dir, exist_ok=True)
    server.file_store.save_to_directory(output_dir)
    server.save_transcript(os.path.join(output_dir, "transcript.json"))

    print("[7/7] Results saved to test_output/")
    print()
    print("=" * 65)
    print(f"  Messages exchanged: {len(server.transcript)}")
    print(f"  Files in workspace: {len(server.file_store.files)}")
    print("=" * 65)

    # Cleanup
    heartbeat_task.cancel()
    ws_server.close()
    await ws_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
