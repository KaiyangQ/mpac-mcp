#!/usr/bin/env python3
"""
Test the interactive agent flow by simulating user input.
Runs both agents with pre-defined commands to verify the full interactive experience.
"""
import asyncio
import json
import logging
import os
import sys
import unittest.mock

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

sys.path.insert(0, os.path.join(REPO_ROOT,
    "examples/two_machine_demo/host", ".venv", "lib", "python3.9", "site-packages"))

from mpac_protocol import MPACServer, MPACAgent

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

with open(os.path.join(REPO_ROOT, "examples/two_machine_demo/host", "config.json")) as f:
    cfg = json.load(f)["anthropic"]

SESSION_ID = "interactive-test-001"
PORT = 8767
WORKSPACE = os.path.join(REPO_ROOT, "examples/two_machine_demo/host", "workspace")


async def simulate_agent(agent, commands):
    """Run interactive agent with simulated user input."""
    input_iter = iter(commands)

    def fake_input(prompt=""):
        try:
            cmd = next(input_iter)
            print(f"{prompt}{cmd}")  # Echo the "typed" command
            return cmd
        except StopIteration:
            return "quit"

    # Patch input() to use our fake commands
    with unittest.mock.patch('builtins.input', side_effect=fake_input):
        await agent.run_interactive()


async def main():
    print("=" * 65)
    print("  Interactive Agent Test — Simulating two users")
    print("=" * 65)
    print()

    # 1. Start coordinator
    server = MPACServer(
        session_id=SESSION_ID,
        host="0.0.0.0",
        port=PORT,
        workspace_dir=WORKSPACE,
    )
    ws_server, heartbeat_task = await server.run_background()
    await asyncio.sleep(0.5)

    # 2. Create agents
    alice = MPACAgent(
        name="Alice",
        api_key=cfg["api_key"],
        model=cfg.get("model", "claude-sonnet-4-6"),
        role_description="Security engineer — fixes auth bugs",
    )
    bob = MPACAgent(
        name="Bob",
        api_key=cfg["api_key"],
        model=cfg.get("model", "claude-sonnet-4-6"),
        role_description="API quality engineer — adds logging and validation",
    )

    # 3. Connect both
    await alice.connect(f"ws://localhost:{PORT}", SESSION_ID)
    await bob.connect(f"ws://localhost:{PORT}", SESSION_ID)

    # 4. Simulate interactive sessions
    # Alice: view auth.py, then fix it
    alice_commands = [
        "view auth.py",
        "task Fix the token expiry bug and timing side-channel in auth.py",
        "quit",
    ]

    # Bob: view api.py, then fix it
    bob_commands = [
        "view api.py",
        "task Add request logging and input validation to api.py",
        "quit",
    ]

    # Run both agents with their simulated commands
    await asyncio.gather(
        simulate_agent(alice, alice_commands),
        simulate_agent(bob, bob_commands),
    )

    # 5. Cleanup
    await alice.close()
    await bob.close()

    # 6. Show final state
    print()
    print("=" * 65)
    print("  FINAL WORKSPACE STATE")
    print("=" * 65)
    for path, info in sorted(server.file_store.files.items()):
        print(f"  {path}: {info['state_ref']} ({len(info['content'])} bytes)")
    print(f"\n  Total messages: {len(server.transcript)}")
    print("=" * 65)

    heartbeat_task.cancel()
    ws_server.close()
    await ws_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
