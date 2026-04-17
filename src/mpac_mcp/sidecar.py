"""Run a local MPAC sidecar for the current workspace."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _compat import ensure_local_mpac_import
    from config import build_bridge_config
    from auth import build_env_verifier, DEFAULT_ENV_VAR
else:
    from ._compat import ensure_local_mpac_import
    from .config import build_bridge_config
    from .auth import build_env_verifier, DEFAULT_ENV_VAR

ensure_local_mpac_import()

from mpac_protocol import MPACServer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local MPAC sidecar.")
    parser.add_argument("--workspace", help="Workspace/repository root")
    parser.add_argument("--host", help="Host to bind", default=None)
    parser.add_argument("--port", help="Port to bind", type=int, default=None)
    parser.add_argument("--session-id", help="Explicit session id (single-session mode only)", default=None)
    parser.add_argument(
        "--multi-session",
        action="store_true",
        help=(
            "Serve multiple sessions from one port. Sessions are created on "
            "demand from the URL path /session/<id>. Incompatible with "
            "--session-id and --workspace (each session gets its own empty "
            "workspace; load files via OP_COMMIT if needed)."
        ),
    )
    parser.add_argument(
        "--security-profile",
        choices=["open", "authenticated", "verified"],
        default=None,
        help=(
            "Security profile (Section 23.1). Defaults to 'authenticated' "
            f"when ${DEFAULT_ENV_VAR} is set, otherwise 'open'."
        ),
    )
    parser.add_argument(
        "--tls",
        action="store_true",
        help="Hint that a TLS-terminating reverse proxy will front this sidecar (display only; affects the banner URL scheme)",
    )
    return parser


def _resolve_security_profile(args_profile: str | None, verifier_present: bool) -> str:
    """Pick the security profile, honoring --security-profile and env."""
    if args_profile is not None:
        return args_profile
    # If a token table is configured, default to authenticated so that the
    # verifier actually gets enforced. Otherwise fall back to open.
    return "authenticated" if verifier_present else "open"


async def run_sidecar(args: argparse.Namespace) -> None:
    # Build credential verifier from env var first (None if unset).
    verifier = build_env_verifier()
    profile = _resolve_security_profile(args.security_profile, verifier is not None)

    if args.multi_session:
        if args.session_id is not None:
            raise SystemExit(
                "--session-id is not allowed with --multi-session; sessions "
                "are created on demand from URL paths like /session/<id>."
            )
        host = args.host or os.environ.get("MPAC_SIDECAR_HOST", "0.0.0.0")
        port = args.port or int(os.environ.get("MPAC_SIDECAR_PORT", "8766"))

        if host not in ("127.0.0.1", "localhost"):
            display_host = host if host != "0.0.0.0" else "<this-host>"
            scheme = "wss" if args.tls else "ws"
            print(
                "[mpac-mcp-sidecar] hosted multi-session banner\n"
                f"  bind             : {host}:{port}\n"
                f"  mode             : multi_session (lazy sessions from URL path)\n"
                f"  security_profile : {profile}\n"
                f"  verifier         : {'env-based (MPAC_TOKEN_TABLE)' if verifier else 'NONE'}\n"
                f"  client URL       : {scheme}://{display_host}:{port}/session/<id>\n"
                f"  auth             : {'handled by reverse proxy' if args.tls else 'NONE at transport layer (dev only)'}",
                flush=True,
            )

        if profile != "open" and verifier is None:
            print(
                f"[mpac-mcp-sidecar] WARNING: security_profile='{profile}' without "
                f"a credential verifier. Set ${DEFAULT_ENV_VAR} to enable per-token "
                "authorization, or pass --security-profile=open to disable.",
                flush=True,
            )

        server = MPACServer(
            multi_session=True,
            host=host,
            port=port,
            credential_verifier=verifier,
            security_profile=profile,
        )
        await server.run()
        return

    # ── Single-session path (backward compatible) ──
    config = build_bridge_config(args.workspace)
    session_id = args.session_id or config.session_id
    host = args.host or config.host
    port = args.port or config.port
    workspace = Path(args.workspace or config.workspace_dir).expanduser().resolve()

    if host not in ("127.0.0.1", "localhost"):
        display_host = host if host != "0.0.0.0" else "<this-host>"
        scheme = "wss" if args.tls else "ws"
        print(
            "[mpac-mcp-sidecar] hosted single-session banner\n"
            f"  bind             : {host}:{port}\n"
            f"  session_id       : {session_id}\n"
            f"  workspace        : {workspace}\n"
            f"  security_profile : {profile}\n"
            f"  verifier         : {'env-based (MPAC_TOKEN_TABLE)' if verifier else 'NONE'}\n"
            f"  client URL       : {scheme}://{display_host}:{port}/session/{session_id}\n"
            f"  auth             : {'handled by reverse proxy' if args.tls else 'NONE (dev only — put a TLS proxy + bearer check in front for production)'}",
            flush=True,
        )

    server = MPACServer(
        session_id=session_id,
        host=host,
        port=port,
        workspace_dir=str(workspace),
        credential_verifier=verifier,
        security_profile=profile,
    )
    await server.run()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    asyncio.run(run_sidecar(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
