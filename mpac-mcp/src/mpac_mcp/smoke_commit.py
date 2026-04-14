"""End-to-end smoke test for begin_task + submit_change + yield_task."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import shutil
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from coordinator_bridge import (
        begin_task,
        fetch_file_state,
        launch_ephemeral_sidecar,
        stop_sidecar,
        submit_change,
        who_is_working,
        yield_task,
    )
else:
    from .coordinator_bridge import (
        begin_task,
        fetch_file_state,
        launch_ephemeral_sidecar,
        stop_sidecar,
        submit_change,
        who_is_working,
        yield_task,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run begin_task/submit_change/yield_task smoke test.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    return parser


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-commit-")
    temp_root = Path(temp_dir.name)
    source_file = source_root / file_path
    target_file = temp_root / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# commit smoke\n", encoding="utf-8")
    return temp_dir


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    config, sidecar_process = await launch_ephemeral_sidecar(temp_dir.name)
    try:
        before = await fetch_file_state(config, args.file)
        if before is None:
            print(f"File not found in sidecar workspace: {args.file}")
            return 1

        task = await begin_task(
            f"Add a temporary MPAC coordination note to {args.file}",
            [args.file],
            config.workspace_dir,
        )

        updated_content = before["content"] + "\n<!-- mpac-mcp smoke commit -->\n"
        commit = await submit_change(
            task["intent_id"],
            args.file,
            updated_content,
            before["state_ref"],
            config.workspace_dir,
        )

        after_commit = await fetch_file_state(config, args.file)
        yielded = await yield_task(task["intent_id"], "smoke_complete", config.workspace_dir)
        summary = await who_is_working(config.workspace_dir)

        print("Commit Smoke Summary")
        print(f"  Source workspace: {Path(args.workspace).expanduser().resolve()}")
        print(f"  Scratch workspace:{summary['workspace_dir']}")
        print(f"  Session:          {summary['session_id']}")
        print(f"  Begin status:     {task['status']}")
        print(f"  Commit status:    {commit['status']}")
        print(f"  Yield status:     {yielded['status']}")
        print(f"  Before ref:       {before['state_ref']}")
        print(f"  After ref:        {after_commit['state_ref'] if after_commit else 'missing'}")
        print(f"  Active intents:   {summary['active_intent_count']}")

        passed = (
            task["status"] == "ok"
            and commit["status"] == "success"
            and after_commit is not None
            and after_commit["state_ref"] != before["state_ref"]
            and yielded["status"] == "ok"
        )
        return 0 if passed else 1
    finally:
        stop_sidecar(sidecar_process)
        temp_dir.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
