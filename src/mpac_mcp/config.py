"""Configuration and path helpers for mpac-mcp."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_SIDECAR_HOST = "127.0.0.1"
DEFAULT_PORT_BASE = 38000
DEFAULT_PORT_SPAN = 2000


@dataclass(frozen=True)
class BridgeConfig:
    """Resolved coordinator configuration for one MCP bridge session.

    Two shapes:
    - **local** (default): an auto-started sidecar bound to 127.0.0.1 on a
      workspace-derived port. ``uri_override`` is None and ``auth_token`` is
      None.
    - **remote**: a pre-existing hosted coordinator reached via
      ``uri_override`` (set through ``MPAC_COORDINATOR_URL``). The bridge must
      not try to spawn a local sidecar in this mode.
    """

    workspace_dir: Path
    session_id: str
    host: str
    port: int
    uri_override: str | None = None
    auth_token: str | None = None
    session_id_pinned: bool = True

    @property
    def uri(self) -> str:
        if self.uri_override:
            return self.uri_override
        return f"ws://{self.host}:{self.port}"

    @property
    def is_remote(self) -> bool:
        return self.uri_override is not None


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


def _extract_session_id_from_url(url: str) -> str | None:
    """Parse a session id from the path of a remote coordinator URL.

    Accepts ``wss://host/session/<id>`` and returns ``<id>``. Returns None
    for any other shape so the caller can fall back to env or derived values.
    """
    parsed = urlparse(url)
    segments = [seg for seg in parsed.path.split("/") if seg]
    if len(segments) >= 2 and segments[0] == "session":
        return segments[1]
    return None


def build_bridge_config(start: str | Path | None = None) -> BridgeConfig:
    """Build a coordinator configuration for the current workspace.

    When ``MPAC_COORDINATOR_URL`` is set, builds a remote config pointing at
    a hosted coordinator. Otherwise builds a local-sidecar config using the
    workspace-derived host/port, preserving the original behaviour.
    """
    workspace = detect_workspace_dir(start)
    remote_url = os.environ.get("MPAC_COORDINATOR_URL")

    if remote_url:
        explicit_session = os.environ.get("MPAC_SESSION_ID")
        url_session = _extract_session_id_from_url(remote_url)
        session_id = explicit_session or url_session or derive_session_id(workspace)
        pinned = bool(explicit_session or url_session)
        parsed = urlparse(remote_url)
        host = parsed.hostname or DEFAULT_SIDECAR_HOST
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        return BridgeConfig(
            workspace_dir=workspace,
            session_id=session_id,
            host=host,
            port=port,
            uri_override=remote_url,
            auth_token=os.environ.get("MPAC_COORDINATOR_TOKEN"),
            session_id_pinned=pinned,
        )

    return BridgeConfig(
        workspace_dir=workspace,
        session_id=derive_session_id(workspace),
        host=os.environ.get("MPAC_SIDECAR_HOST", DEFAULT_SIDECAR_HOST),
        port=derive_sidecar_port(workspace),
    )
