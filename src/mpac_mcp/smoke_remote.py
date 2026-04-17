"""End-to-end smoke test for remote-coordinator mode.

Simulates an externally-hosted MPAC coordinator by spawning a sidecar on a
fixed 127.0.0.1 port with a caller-chosen session id, then drives the MCP
bridge through ``MPAC_COORDINATOR_URL`` so no local sidecar auto-start is
involved. Verifies:

  * ``BridgeConfig.is_remote`` is True and ``uri_override`` wins
  * ``who_is_working`` / ``begin_task`` / ``check_overlap`` all succeed
  * the bridge does not spawn a second sidecar process
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _sidecar_script_path() -> Path:
    return Path(__file__).resolve().with_name("sidecar.py")


def _prepare_workspace(source_workspace: str | Path, file_path: str) -> tempfile.TemporaryDirectory:
    source_root = Path(source_workspace).expanduser().resolve()
    temp_dir = tempfile.TemporaryDirectory(prefix="mpac-mcp-remote-")
    target_file = Path(temp_dir.name) / file_path
    target_file.parent.mkdir(parents=True, exist_ok=True)
    source_file = source_root / file_path
    if source_file.exists():
        shutil.copy2(source_file, target_file)
    else:
        target_file.write_text("# remote smoke\n", encoding="utf-8")
    return temp_dir


def _start_hosted_sidecar(
    workspace: str,
    host: str,
    port: int,
    session_id: str,
) -> subprocess.Popen:
    """Spawn a sidecar with a clean env so MPAC_COORDINATOR_URL does not leak in."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MPAC_COORDINATOR")}
    env.pop("MPAC_SESSION_ID", None)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.Popen(
        [
            sys.executable,
            str(_sidecar_script_path()),
            "--workspace",
            workspace,
            "--host",
            host,
            "--port",
            str(port),
            "--session-id",
            session_id,
        ],
        env=env,
        cwd=workspace,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


async def _wait_for_ready(uri: str, timeout_sec: float = 5.0) -> None:
    import websockets
    import json

    deadline = time.time() + timeout_sec
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({"type": "SESSION_SUMMARY"}))
                await asyncio.wait_for(ws.recv(), timeout=1.0)
                return
        except Exception as exc:
            last_err = exc
            await asyncio.sleep(0.15)
    raise RuntimeError(f"Hosted sidecar at {uri} never became ready: {last_err}")


async def run_smoke(args: argparse.Namespace) -> int:
    temp_dir = _prepare_workspace(args.workspace, args.file)
    workspace = temp_dir.name
    host = "127.0.0.1"
    port = _find_free_port()
    session_id = f"mpac-remote-smoke-{port}"
    remote_url = f"ws://{host}:{port}/session/{session_id}"

    sidecar = _start_hosted_sidecar(workspace, host, port, session_id)
    passed = False
    try:
        await _wait_for_ready(f"ws://{host}:{port}")

        os.environ["MPAC_COORDINATOR_URL"] = remote_url
        os.environ["MPAC_WORKSPACE_DIR"] = workspace
        os.environ.pop("MPAC_COORDINATOR_TOKEN", None)

        # Import after env is set so build_bridge_config reads remote mode
        from mpac_mcp.config import build_bridge_config
        from mpac_mcp.coordinator_bridge import (
            begin_task,
            check_overlap,
            who_is_working,
            yield_task,
        )

        config = build_bridge_config(workspace)
        assert config.is_remote, "BridgeConfig should be remote"
        assert config.uri == remote_url
        assert config.session_id == session_id

        view = await who_is_working(workspace)
        begun = await begin_task(
            f"Remote-mode edit on {args.file}",
            [args.file],
            workspace,
        )
        overlap = await check_overlap([args.file], workspace)
        yielded = None
        if begun["status"] == "ok":
            yielded = await yield_task(begun["intent_id"], "remote_smoke_done", workspace)

        print("Remote Smoke Summary")
        print(f"  Source workspace : {Path(args.workspace).expanduser().resolve()}")
        print(f"  Scratch workspace: {workspace}")
        print(f"  Remote URL       : {remote_url}")
        print(f"  Session id       : {session_id}")
        print(f"  is_remote        : {config.is_remote}")
        print(f"  who_is_working   : {view['participant_count']} participants, "
              f"{view['active_intent_count']} intents")
        print(f"  begin_task       : status={begun['status']}, "
              f"intent_id={begun.get('intent_id')}")
        print(f"  check_overlap    : has_overlap={overlap['has_overlap']}")
        if yielded is not None:
            print(f"  yield_task       : status={yielded['status']}")

        passed = (
            config.is_remote
            and begun["status"] == "ok"
            and view["session_id"] == session_id
            and (yielded is None or yielded["status"] == "ok")
        )
        return 0 if passed else 1
    finally:
        if sidecar.poll() is None:
            sidecar.terminate()
            try:
                sidecar.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                sidecar.kill()
        temp_dir.cleanup()
        os.environ.pop("MPAC_COORDINATOR_URL", None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run remote-mode smoke test.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--file", default="README.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_smoke(args))


if __name__ == "__main__":
    raise SystemExit(main())
