from pathlib import Path

from mpac_mcp.claude_setup import build_local_command, build_project_config


def test_build_local_command_contains_expected_parts():
    repo_root = Path("/tmp/example-repo")
    command = build_local_command(repo_root)
    assert "claude mcp add" in command
    assert "MPAC_WORKSPACE_DIR=/tmp/example-repo" in command
    assert "python3" in command
    assert "mpac-mcp/src/mpac_mcp/server.py" in command


def test_build_project_config_has_stdio_server():
    repo_root = Path("/tmp/example-repo")
    payload = build_project_config(repo_root)
    server = payload["mcpServers"]["mpac-coding"]
    assert server["type"] == "stdio"
    assert server["command"] == "python3"
    assert server["env"]["MPAC_WORKSPACE_DIR"] == "/tmp/example-repo"
