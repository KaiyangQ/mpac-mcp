"""Configuration and path helpers for mpac-mcp."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path


DEFAULT_SIDECAR_HOST = "127.0.0.1"
DEFAULT_PORT_BASE = 38000
DEFAULT_PORT_SPAN = 2000


@dataclass(frozen=True)
class BridgeConfig:
    """Resolved local sidecar configuration for a repository."""

    workspace_dir: Path
    session_id: str
    host: str
    port: int

    @property
    def uri(self) -> str:
        return f"ws://{self.host}:{self.port}"


def detect_workspace_dir(start: str | Path | None = None) -> Path:
    """Resolve the repository/workspace root for the current invocation."""
    env_override = os.environ.get("MPAC_WORKSPACE_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    current = Path(start or os.getcwd()).expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def derive_session_id(workspace_dir: str | Path) -> str:
    """Derive a stable local session id from the workspace path."""
    resolved = Path(workspace_dir).expanduser().resolve()
    slug = resolved.name.replace(" ", "-").lower() or "workspace"
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()[:10]
    return f"mpac-local-{slug}-{digest}"


def derive_sidecar_port(workspace_dir: str | Path) -> int:
    """Derive a deterministic localhost port from the workspace path."""
    env_override = os.environ.get("MPAC_SIDECAR_PORT")
    if env_override:
        return int(env_override)

    resolved = Path(workspace_dir).expanduser().resolve()
    digest = hashlib.sha1(str(resolved).encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16) % DEFAULT_PORT_SPAN
    return DEFAULT_PORT_BASE + offset


def build_bridge_config(start: str | Path | None = None) -> BridgeConfig:
    """Build a complete bridge configuration for the current workspace."""
    workspace = detect_workspace_dir(start)
    return BridgeConfig(
        workspace_dir=workspace,
        session_id=derive_session_id(workspace),
        host=os.environ.get("MPAC_SIDECAR_HOST", DEFAULT_SIDECAR_HOST),
        port=derive_sidecar_port(workspace),
    )

