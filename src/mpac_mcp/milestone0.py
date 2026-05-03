"""Milestone 0 smoke test: two processes share one local coordinator."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from coordinator_bridge import launch_ephemeral_sidecar, stop_sidecar, who_is_working
else:
    from .coordinator_bridge import launch_ephemeral_sidecar, stop_sidecar, who_is_working


def _client_script_path() -> Path:
    return Path(__file__).resolve().with_name("dev_client.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MPAC Milestone 0 smoke test.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--hold-sec", type=float, default=4.0)
    return parser


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-milestone0-")
    temp_root = Path(temp_dir.name)
    source_file = source_root / file_path
    target_file = temp_root / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# milestone0 smoke\n", encoding="utf-8")
    return temp_dir


def _finish_process(process: subprocess.Popen, timeout: float) -> None:
    try:
        process.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    config, sidecar_process = await launch_ephemeral_sidecar(temp_dir.name)
    file_path = args.file

    clients = []
    try:
        clients = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(_client_script_path()),
                    "--uri",
                    config.uri,
                    "--session-id",
                    config.session_id,
                    "--name",
                    "Alice",
                    "--objective",
                    f"Refactor {file_path} for auth hardening",
                    "--file",
                    file_path,
                    "--hold-sec",
                    str(args.hold_sec),
                ],
                cwd=str(config.workspace_dir),
                start_new_session=True,
            ),
            subprocess.Popen(
                [
                    sys.executable,
                    str(_client_script_path()),
                    "--uri",
                    config.uri,
                    "--session-id",
                    config.session_id,
                    "--name",
                    "Bob",
                    "--objective",
                    f"Add logging to {file_path}",
                    "--file",
                    file_path,
                    "--hold-sec",
                    str(args.hold_sec),
                ],
                cwd=str(config.workspace_dir),
                start_new_session=True,
            ),
        ]

        await asyncio.sleep(1.5)
        summary = await who_is_working(config.workspace_dir)

        # Same-file scope is now race-locked at INTENT_ANNOUNCE. The second
        # client stays connected, but its overlapping intent is rejected with
        # STALE_INTENT instead of becoming an open advisory conflict.
        passed = (
            summary["participant_count"] >= 2
            and summary["active_intent_count"] == 1
            and summary["open_conflict_count"] == 0
        )

        print("Milestone 0 Summary")
        print(f"  Source workspace: {Path(args.workspace).expanduser().resolve()}")
        print(f"  Scratch workspace:{summary['workspace_dir']}")
        print(f"  Sidecar URI:      {summary['sidecar_uri']}")
        print(f"  Session ID:       {summary['session_id']}")
        print(f"  Participants:     {summary['participant_count']}")
        print(f"  Active intents:   {summary['active_intent_count']}")
        print(f"  Open conflicts:   {summary['open_conflict_count']}")
        for intent in summary["active_intents"]:
            print(
                f"  - {intent['principal_id']}: {intent['objective']} "
                f"{intent.get('scope', {})}"
            )

        return 0 if passed else 1
    finally:
        deadline = time.time() + args.hold_sec + 2.0
        try:
            for client in clients:
                timeout = max(0.1, deadline - time.time())
                _finish_process(client, timeout)
        finally:
            stop_sidecar(sidecar_process)
            temp_dir.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
