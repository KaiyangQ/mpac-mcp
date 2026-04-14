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
    parser.add_argument(
        "--tls",
        action="store_true",
        help="Hint that a TLS-terminating reverse proxy will front this sidecar (display only; affects the banner URL scheme)",
    )
    return parser


async def run_sidecar(args: argparse.Namespace) -> None:
    config = build_bridge_config(args.workspace)
    session_id = args.session_id or config.session_id
    host = args.host or config.host
    port = args.port or config.port
    workspace = Path(args.workspace or config.workspace_dir).expanduser().resolve()

    if host not in ("127.0.0.1", "localhost"):
        display_host = host if host != "0.0.0.0" else "<this-host>"
        scheme = "wss" if args.tls else "ws"
        print(
            "[mpac-mcp-sidecar] hosted-mode banner\n"
            f"  bind       : {host}:{port}\n"
            f"  session_id : {session_id}\n"
            f"  workspace  : {workspace}\n"
            f"  client URL : {scheme}://{display_host}:{port}/session/{session_id}\n"
            f"  auth       : {'handled by reverse proxy' if args.tls else 'NONE (dev only — put a TLS proxy + bearer check in front for production)'}",
            flush=True,
        )

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

