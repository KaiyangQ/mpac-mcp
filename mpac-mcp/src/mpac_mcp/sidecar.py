"""Run a local MPAC sidecar for the current workspace."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _compat import ensure_local_mpac_import
    from config import build_bridge_config
else:
    from ._compat import ensure_local_mpac_import
    from .config import build_bridge_config

ensure_local_mpac_import()

from mpac_protocol import MPACServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local MPAC sidecar.")
    parser.add_argument("--workspace", help="Workspace/repository root")
    parser.add_argument("--host", help="Host to bind", default=None)
    parser.add_argument("--port", help="Port to bind", type=int, default=None)
    parser.add_argument("--session-id", help="Explicit session id", default=None)
    return parser


async def run_sidecar(args: argparse.Namespace) -> None:
    config = build_bridge_config(args.workspace)
    session_id = args.session_id or config.session_id
    host = args.host or config.host
    port = args.port or config.port
    workspace = Path(args.workspace or config.workspace_dir).expanduser().resolve()

    server = MPACServer(
        session_id=session_id,
        host=host,
        port=port,
        workspace_dir=str(workspace),
    )
    await server.run()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    asyncio.run(run_sidecar(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

