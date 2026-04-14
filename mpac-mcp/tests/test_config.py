from pathlib import Path

import pytest

from mpac_mcp.config import (
    BridgeConfig,
    build_bridge_config,
    derive_session_id,
    derive_sidecar_port,
)


REMOTE_ENV_KEYS = (
    "MPAC_COORDINATOR_URL",
    "MPAC_COORDINATOR_TOKEN",
    "MPAC_SESSION_ID",
    "MPAC_SIDECAR_HOST",
    "MPAC_SIDECAR_PORT",
    "MPAC_WORKSPACE_DIR",
)


@pytest.fixture(autouse=True)
def _clear_remote_env(monkeypatch):
    for key in REMOTE_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


def test_derive_sidecar_port_is_stable():
    workspace = Path("/tmp/example-workspace")
    assert derive_sidecar_port(workspace) == derive_sidecar_port(workspace)


def test_derive_session_id_is_stable():
    workspace = Path("/tmp/example-workspace")
    assert derive_session_id(workspace) == derive_session_id(workspace)


def test_build_bridge_config_uses_workspace():
    config = build_bridge_config("/tmp/example-workspace")
    assert config.workspace_dir == Path("/tmp/example-workspace").resolve()
    assert config.uri.startswith("ws://127.0.0.1:")
    assert config.is_remote is False
    assert config.session_id_pinned is True
    assert config.auth_token is None


def test_remote_mode_parses_session_id_from_url(monkeypatch):
    monkeypatch.setenv("MPAC_COORDINATOR_URL", "wss://mpac.example.com/session/room-alpha")
    config = build_bridge_config("/tmp/example-workspace")
    assert config.is_remote is True
    assert config.uri == "wss://mpac.example.com/session/room-alpha"
    assert config.session_id == "room-alpha"
    assert config.session_id_pinned is True
    assert config.host == "mpac.example.com"
    assert config.port == 443


def test_remote_mode_explicit_session_env_wins(monkeypatch):
    monkeypatch.setenv("MPAC_COORDINATOR_URL", "wss://mpac.example.com/session/url-room")
    monkeypatch.setenv("MPAC_SESSION_ID", "env-room")
    config = build_bridge_config("/tmp/example-workspace")
    assert config.session_id == "env-room"
    assert config.session_id_pinned is True


def test_remote_mode_without_session_id_is_unpinned(monkeypatch):
    monkeypatch.setenv("MPAC_COORDINATOR_URL", "ws://127.0.0.1:9999")
    config = build_bridge_config("/tmp/example-workspace")
    assert config.is_remote is True
    assert config.uri == "ws://127.0.0.1:9999"
    assert config.session_id_pinned is False
    assert config.session_id.startswith("mpac-local-")


def test_remote_mode_auth_token(monkeypatch):
    monkeypatch.setenv("MPAC_COORDINATOR_URL", "wss://mpac.example.com/session/room-a")
    monkeypatch.setenv("MPAC_COORDINATOR_TOKEN", "secret-abc")
    config = build_bridge_config("/tmp/example-workspace")
    assert config.auth_token == "secret-abc"


def test_local_mode_unchanged_when_remote_env_absent():
    config = build_bridge_config("/tmp/example-workspace")
    assert config.uri_override is None
    assert config.auth_token is None
    assert config.is_remote is False
    assert config.host == "127.0.0.1"


def test_remote_config_is_frozen():
    config = BridgeConfig(
        workspace_dir=Path("/tmp/example"),
        session_id="room-a",
        host="mpac.example.com",
        port=443,
        uri_override="wss://mpac.example.com/session/room-a",
    )
    with pytest.raises(Exception):
        config.session_id = "other"  # type: ignore[misc]
