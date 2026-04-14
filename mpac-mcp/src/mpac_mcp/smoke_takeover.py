"""End-to-end smoke test for claiming a suspended task."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from coordinator_bridge import (
        launch_ephemeral_sidecar,
        stop_sidecar,
        take_over_task,
        who_is_working,
        yield_task,
    )
else:
    from .coordinator_bridge import (
        launch_ephemeral_sidecar,
        stop_sidecar,
        take_over_task,
        who_is_working,
        yield_task,
    )


def _client_script_path() -> Path:
    return Path(__file__).resolve().with_name("dev_client.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run claim/takeover smoke test.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--hold-sec", type=float, default=1.0)
    return parser


def _spawn_suspending_client(
    *,
    uri: str,
    session_id: str,
    workspace_dir: str,
    file_path: str,
    hold_sec: float,
) -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            str(_client_script_path()),
            "--uri",
            uri,
            "--session-id",
            session_id,
            "--name",
            "Alice",
            "--roles",
            "contributor",
            "--objective",
            f"Leave a suspended task on {file_path}",
            "--file",
            file_path,
            "--hold-sec",
            str(hold_sec),
            "--goodbye-disposition",
            "transfer",
        ],
        cwd=workspace_dir,
        start_new_session=True,
    )


def _set_bridge_identity() -> dict[str, str | None]:
    previous = {
        "MPAC_AGENT_NAME": os.environ.get("MPAC_AGENT_NAME"),
        "MPAC_PRINCIPAL_ID": os.environ.get("MPAC_PRINCIPAL_ID"),
        "MPAC_AGENT_ROLES": os.environ.get("MPAC_AGENT_ROLES"),
    }
    os.environ["MPAC_AGENT_NAME"] = "BridgeClaimer"
    os.environ["MPAC_PRINCIPAL_ID"] = "agent:bridge-claimer"
    os.environ["MPAC_AGENT_ROLES"] = "contributor"
    return previous


def _restore_bridge_identity(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-takeover-")
    temp_root = Path(temp_dir.name)
    source_file = source_root / file_path
    target_file = temp_root / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# takeover smoke\n", encoding="utf-8")
    return temp_dir


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    config, sidecar_process = await launch_ephemeral_sidecar(temp_dir.name)
    previous_env = _set_bridge_identity()
    try:
        owner = _spawn_suspending_client(
            uri=config.uri,
            session_id=config.session_id,
            workspace_dir=str(config.workspace_dir),
            file_path=args.file,
            hold_sec=args.hold_sec,
        )
        owner.wait(timeout=args.hold_sec + 3.0)
        await asyncio.sleep(0.3)

        before = await who_is_working(config.workspace_dir)
        suspended = next(
            (
                intent
                for intent in before.get("active_intents", [])
                if intent.get("principal_id") == "agent:Alice"
                and intent.get("state") == "SUSPENDED"
            ),
            None,
        )
        if suspended is None:
            print("No suspended intent found for takeover smoke.")
            return 1

        takeover = await take_over_task(
            suspended["intent_id"],
            config.workspace_dir,
            justification="Resume work after the original owner left cleanly",
        )
        after = await who_is_working(config.workspace_dir)
        if takeover.get("status") == "ok":
            await yield_task(
                takeover["new_intent_id"],
                "smoke_takeover_complete",
                config.workspace_dir,
            )

        print("Takeover Smoke Summary")
        print(f"  Source workspace:  {Path(args.workspace).expanduser().resolve()}")
        print(f"  Scratch workspace: {config.workspace_dir}")
        print(f"  Session:           {config.session_id}")
        print(f"  Suspended intent:  {suspended['intent_id']}")
        print(f"  Takeover status:   {takeover['status']}")
        print(f"  Takeover decision: {takeover['decision']}")
        print(f"  New intent:        {takeover['new_intent_id']}")
        print(f"  Active intents:    {after['active_intent_count']}")

        passed = (
            takeover["status"] == "ok"
            and takeover["decision"] == "approved"
            and any(
                intent.get("intent_id") == takeover["new_intent_id"]
                and intent.get("principal_id") == "agent:bridge-claimer"
                for intent in after.get("active_intents", [])
            )
        )
        return 0 if passed else 1
    finally:
        _restore_bridge_identity(previous_env)
        stop_sidecar(sidecar_process)
        temp_dir.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
