"""Helpers for wiring mpac-mcp into Claude Code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import detect_workspace_dir
else:
    from .config import detect_workspace_dir


def build_local_command(repo_root: Path, scope: str = "local", name: str = "mpac-coding") -> str:
    """Build a Claude Code `claude mcp add` command for this repo."""
    server_script = repo_root / "mpac-mcp" / "src" / "mpac_mcp" / "server.py"
    pythonpath = f"{repo_root / 'mpac-mcp' / 'src'}:{repo_root / 'mpac-package' / 'src'}"

    parts = [
        "claude",
        "mcp",
        "add",
        "--transport",
        "stdio",
        "--scope",
        scope,
        "--env",
        f"PYTHONPATH={pythonpath}",
        "--env",
        f"MPAC_WORKSPACE_DIR={repo_root}",
        name,
        "--",
        "python3",
        str(server_script),
    ]
    return " ".join(shlex.quote(part) for part in parts)


def build_project_config(repo_root: Path, name: str = "mpac-coding") -> dict:
    """Build a `.mcp.json` payload for this repository."""
    return {
        "mcpServers": {
            name: {
                "type": "stdio",
                "command": "python3",
                "args": [str(repo_root / "mpac-mcp" / "src" / "mpac_mcp" / "server.py")],
                "env": {
                    "PYTHONPATH": (
                        f"{repo_root / 'mpac-mcp' / 'src'}:"
                        f"{repo_root / 'mpac-package' / 'src'}"
                    ),
                    "MPAC_WORKSPACE_DIR": str(repo_root),
                },
            }
        }
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Claude Code config for mpac-mcp.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--scope", default="local", choices=["local", "project", "user"])
    parser.add_argument("--name", default="mpac-coding")
    parser.add_argument(
        "--format",
        default="command",
        choices=["command", "json"],
        help="Print a `claude mcp add` command or a `.mcp.json` payload",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = detect_workspace_dir(args.workspace)

    if args.format == "json":
        print(json.dumps(build_project_config(repo_root, args.name), indent=2))
    else:
        print(build_local_command(repo_root, scope=args.scope, name=args.name))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
