"""End-to-end smoke test for conflict acknowledgment, escalation, and resolution."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from coordinator_bridge import (
        ack_conflict,
        begin_task,
        escalate_conflict,
        launch_ephemeral_sidecar,
        resolve_conflict,
        stop_sidecar,
        who_is_working,
        yield_task,
    )
else:
    from .coordinator_bridge import (
        ack_conflict,
        begin_task,
        escalate_conflict,
        launch_ephemeral_sidecar,
        resolve_conflict,
        stop_sidecar,
        who_is_working,
        yield_task,
    )


def _client_script_path() -> Path:
    return Path(__file__).resolve().with_name("dev_client.py")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run ack/escalate/resolve governance smoke test."
    )
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    parser.add_argument("--hold-sec", type=float, default=6.0)
    return parser


def _spawn_dev_client(
    *,
    uri: str,
    session_id: str,
    workspace_dir: str,
    name: str,
    roles: str,
    hold_sec: float,
    objective: str | None = None,
    file_path: str | None = None,
) -> subprocess.Popen:
    cmd = [
        sys.executable,
        str(_client_script_path()),
        "--uri",
        uri,
        "--session-id",
        session_id,
        "--name",
        name,
        "--roles",
        roles,
        "--hold-sec",
        str(hold_sec),
    ]
    if objective and file_path:
        cmd.extend(["--objective", objective, "--file", file_path])
    return subprocess.Popen(
        cmd,
        cwd=workspace_dir,
        start_new_session=True,
    )


def _set_bridge_identity(name: str, principal_id: str, roles: str) -> dict[str, str | None]:
    previous = {
        "MPAC_AGENT_NAME": os.environ.get("MPAC_AGENT_NAME"),
        "MPAC_PRINCIPAL_ID": os.environ.get("MPAC_PRINCIPAL_ID"),
        "MPAC_AGENT_ROLES": os.environ.get("MPAC_AGENT_ROLES"),
    }
    os.environ["MPAC_AGENT_NAME"] = name
    os.environ["MPAC_PRINCIPAL_ID"] = principal_id
    os.environ["MPAC_AGENT_ROLES"] = roles
    return previous


def _restore_bridge_identity(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-governance-")
    temp_root = Path(temp_dir.name)
    source_file = source_root / file_path
    target_file = temp_root / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# governance smoke\n", encoding="utf-8")
    return temp_dir


async def _wait_for_conflict(
    workspace_dir: str | Path,
    intent_id: str,
    *,
    timeout_sec: float = 3.0,
) -> tuple[dict | None, dict]:
    deadline = time.time() + timeout_sec
    latest_summary: dict = {"open_conflicts": []}
    while time.time() < deadline:
        latest_summary = await who_is_working(workspace_dir)
        conflict = next(
            (
                item
                for item in latest_summary.get("open_conflicts", [])
                if intent_id in {item.get("intent_a"), item.get("intent_b")}
            ),
            None,
        )
        if conflict is not None:
            return conflict, latest_summary
        await asyncio.sleep(0.2)
    return None, latest_summary


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    workspace_dir = temp_dir.name
    config, sidecar_process = await launch_ephemeral_sidecar(workspace_dir)
    alice = _spawn_dev_client(
        uri=config.uri,
        session_id=config.session_id,
        workspace_dir=str(config.workspace_dir),
        name="Alice",
        roles="contributor",
        hold_sec=args.hold_sec,
        objective=f"Refactor {args.file} for a governance smoke",
        file_path=args.file,
    )

    arbiter = None
    previous_env = _set_bridge_identity(
        "BridgeWorker",
        "agent:bridge-worker",
        "contributor",
    )
    begun = acked = escalated = resolved = None
    after = None
    conflict_id = None
    try:
        await asyncio.sleep(1.0)
        begun = await begin_task(
            f"Add a coordination banner to {args.file}",
            [args.file],
            config.workspace_dir,
        )
        conflict, summary = await _wait_for_conflict(
            config.workspace_dir,
            begun["intent_id"],
        )
        conflict_id = conflict.get("conflict_id") if conflict else None
        if conflict_id is None:
            print("No conflict found for governance smoke.")
            print(f"  Begin status: {begun['status']}")
            print(f"  Begin conflict flag: {begun['has_conflict']}")
            print(f"  Participants: {summary.get('participant_count')}")
            print(f"  Active intents: {summary.get('active_intent_count')}")
            print(f"  Open conflicts: {summary.get('open_conflict_count')}")
            return 1

        acked = await ack_conflict(conflict_id, "seen", config.workspace_dir)

        arbiter = _spawn_dev_client(
            uri=config.uri,
            session_id=config.session_id,
            workspace_dir=str(config.workspace_dir),
            name="Arbiter",
            roles="arbiter",
            hold_sec=args.hold_sec,
        )
        await asyncio.sleep(0.8)
        escalated = await escalate_conflict(
            conflict_id,
            "Need arbiter decision for overlapping edit scope",
            config.workspace_dir,
        )

        _set_bridge_identity("BridgeArbiter", "agent:bridge-arbiter", "arbiter")
        resolved = await resolve_conflict(
            conflict_id,
            "approved",
            config.workspace_dir,
            rationale="Arbiter approved the overlap after review",
        )
        _restore_bridge_identity(previous_env)
        previous_env = _set_bridge_identity(
            "BridgeWorker",
            "agent:bridge-worker",
            "contributor",
        )

        if begun and begun.get("status") == "ok":
            await yield_task(
                begun["intent_id"],
                "smoke_governance_complete",
                config.workspace_dir,
            )
        after = await who_is_working(config.workspace_dir)
    finally:
        _restore_bridge_identity(previous_env)
        deadline = time.time() + args.hold_sec + 2.0
        for proc in [alice, arbiter]:
            if proc is None:
                continue
            timeout = max(0.1, deadline - time.time())
            proc.wait(timeout=timeout)
        stop_sidecar(sidecar_process)
        temp_dir.cleanup()

    print("Governance Smoke Summary")
    print(f"  Source workspace:   {Path(args.workspace).expanduser().resolve()}")
    print(f"  Scratch workspace:  {config.workspace_dir}")
    print(f"  Session:            {config.session_id}")
    print(f"  Begin status:       {begun['status'] if begun else 'missing'}")
    print(f"  Conflict id:        {conflict_id or 'missing'}")
    print(f"  Ack status:         {acked['status'] if acked else 'missing'}")
    print(f"  Escalate status:    {escalated['status'] if escalated else 'missing'}")
    print(f"  Escalate target:    {escalated.get('escalate_to') if escalated else 'missing'}")
    print(f"  Resolve status:     {resolved['status'] if resolved else 'missing'}")
    print(f"  Remaining conflicts:{after['open_conflict_count'] if after else 'missing'}")

    passed = (
        begun is not None
        and begun["status"] == "ok"
        and conflict_id is not None
        and acked is not None
        and acked["status"] == "ok"
        and escalated is not None
        and escalated["status"] == "ok"
        and escalated.get("escalate_to") == "agent:Arbiter"
        and resolved is not None
        and resolved["status"] == "ok"
        and resolved.get("remaining_conflict") is None
        and after is not None
        and all(item.get("conflict_id") != conflict_id for item in after.get("open_conflicts", []))
    )
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
