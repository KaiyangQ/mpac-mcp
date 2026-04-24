"""Regression tests for the stdout/stderr handling of `handle_chat()`.

Claude Code CLI writes several user-facing errors to STDOUT, not stderr —
notably "Claude Code on Windows requires git-bash" and "Not logged in".
Pre-0.2.4 relay only surfaced stderr, so these errors reached the web
chat UI as "[relay] Claude Code failed (exit 1):" with an empty body.
These tests lock down the fix: stdout content must survive into the
user-facing error message whenever stderr is empty or both are populated.
"""
import asyncio
from unittest.mock import patch, AsyncMock

import pytest

from mpac_mcp.relay import handle_chat, RelayContext


def _ctx():
    return RelayContext(
        claude_binary="fake-claude",
        project_id=1,
        web_http_url="http://localhost:8001",
        agent_token="test-token",
    )


class FakeProc:
    """Mimics asyncio.subprocess.Process for our tests."""
    def __init__(self, returncode, stdout_bytes, stderr_bytes):
        self.returncode = returncode
        self._stdout = stdout_bytes
        self._stderr = stderr_bytes

    async def communicate(self, input=None):
        return self._stdout, self._stderr


async def _run(proc):
    with patch(
        "mpac_mcp.relay.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ), patch("mpac_mcp.relay._build_mcp_config", return_value="/tmp/fake.json"), \
        patch("mpac_mcp.relay.os.path.exists", return_value=False):
        return await handle_chat(_ctx(), "hi")


def test_error_on_stdout_only_surfaces_to_user():
    # Claude Code CLI's "requires git-bash" error path writes to stdout
    # and leaves stderr empty. Must NOT be swallowed.
    proc = FakeProc(
        returncode=1,
        stdout_bytes=b"Claude Code on Windows requires git-bash",
        stderr_bytes=b"",
    )
    reply = asyncio.run(_run(proc))
    assert "git-bash" in reply, reply
    assert "exit 1" in reply, reply


def test_not_logged_in_on_stdout_triggers_login_hint():
    # "Not logged in" path (also stdout-only) should trigger the
    # dedicated authentication help message, not the generic failure.
    proc = FakeProc(
        returncode=1,
        stdout_bytes=b"Not logged in \xc2\xb7 Please run /login",
        stderr_bytes=b"",
    )
    reply = asyncio.run(_run(proc))
    assert "claude /login" in reply, reply
    assert "Not logged in" in reply, reply


def test_error_on_stderr_still_works():
    # When stderr has content (traditional case), surface it.
    proc = FakeProc(
        returncode=1,
        stdout_bytes=b"",
        stderr_bytes=b"spawn failure: something went wrong",
    )
    reply = asyncio.run(_run(proc))
    assert "something went wrong" in reply, reply


def test_both_streams_populated_both_included():
    # When both have content, we don't know which has the real
    # diagnostic — include both.
    proc = FakeProc(
        returncode=2,
        stdout_bytes=b"stdout diagnostic here",
        stderr_bytes=b"stderr diagnostic here",
    )
    reply = asyncio.run(_run(proc))
    assert "stderr diagnostic here" in reply, reply
    assert "stdout diagnostic here" in reply, reply
    assert "exit 2" in reply, reply


def test_both_streams_empty_shows_placeholder():
    # Pathological case: proc exits non-zero with zero output.
    # User should still get SOMETHING more useful than a colon.
    proc = FakeProc(returncode=137, stdout_bytes=b"", stderr_bytes=b"")
    reply = asyncio.run(_run(proc))
    assert "exit 137" in reply, reply
    assert reply.rstrip().endswith(":") is False, (
        "got empty-body error — regression of the 0.2.3 bug"
    )


def test_successful_run_returns_stdout():
    # Sanity: exit 0 path unchanged — stdout is the reply.
    proc = FakeProc(returncode=0, stdout_bytes=b"Hi there!", stderr_bytes=b"")
    reply = asyncio.run(_run(proc))
    assert reply == "Hi there!"
