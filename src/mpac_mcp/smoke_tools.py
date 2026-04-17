"""End-to-end smoke test for begin_task + check_overlap."""

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
    from coordinator_bridge import (
        begin_task,
        check_overlap,
        launch_ephemeral_sidecar,
        stop_sidecar,
        who_is_working,
        yield_task,
    )
else:
    from .coordinator_bridge import (
        begin_task,
        check_overlap,
        launch_ephemeral_sidecar,
        stop_sidecar,
        who_is_working,
        yield_task,
    )


def _client_script_path() -> Path:
    return Path(__file__).resolve().with_name("dev_client.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run begin_task/check_overlap smoke test.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--hold-sec", type=float, default=4.0)
    return parser


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-tools-")
    temp_root = Path(temp_dir.name)
    source_file = source_root / file_path
    target_file = temp_root / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# tools smoke\n", encoding="utf-8")
    return temp_dir


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    config, sidecar_process = await launch_ephemeral_sidecar(temp_dir.name)

    other = subprocess.Popen(
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
            f"Improve {args.file}",
            "--file",
            args.file,
            "--hold-sec",
            str(args.hold_sec),
        ],
        cwd=str(config.workspace_dir),
        start_new_session=True,
    )

    try:
        await asyncio.sleep(1.0)
        before = await who_is_working(config.workspace_dir)
        begun = await begin_task(
            f"Add coordination notes to {args.file}",
            [args.file],
            config.workspace_dir,
        )
        overlap = await check_overlap([args.file], config.workspace_dir)
        if begun["status"] == "ok":
            await yield_task(begun["intent_id"], "smoke_tools_complete", config.workspace_dir)
        after = await who_is_working(config.workspace_dir)

        print("Tool Smoke Summary")
        print(f"  Source workspace: {Path(args.workspace).expanduser().resolve()}")
        print(f"  Scratch workspace:{before['workspace_dir']}")
        print(f"  Session:          {before['session_id']}")
        print(f"  Before intents:   {before['active_intent_count']}")
        print(f"  Begin status:     {begun['status']}")
        print(f"  Begin conflict:   {begun['has_conflict']}")
        print(f"  Overlap found:    {overlap['has_overlap']}")
        print(f"  After intents:    {after['active_intent_count']}")
        if overlap["overlaps"]:
            first = overlap["overlaps"][0]
            print(
                f"  First overlap:    {first['principal_id']} -> {first['objective']} "
                f"{first['scope']}"
            )

        passed = (
            before["active_intent_count"] >= 1
            and begun["status"] == "ok"
            and begun["has_conflict"] is True
            and overlap["has_overlap"] is True
            and after["active_intent_count"] >= 1
        )
        return 0 if passed else 1
    finally:
        deadline = time.time() + args.hold_sec + 2.0
        timeout = max(0.1, deadline - time.time())
        other.wait(timeout=timeout)
        stop_sidecar(sidecar_process)
        temp_dir.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
