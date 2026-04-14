from pathlib import Path

from mpac_mcp.config import build_bridge_config, derive_session_id, derive_sidecar_port


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
