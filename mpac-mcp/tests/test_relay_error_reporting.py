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


# ── 2026-04-28: orphan-intent cleanup on subprocess failure ─────────────
#
# Motivating bug: a `claude -p` that announced an intent then died (e.g.
# write_project_file got blocked by the API content filter for
# generating 1000 identical "hello world" lines) left an ACTIVE intent
# in the coordinator. The next chat from the same user produced
# ``Dave's Claude ↔ Dave's Claude`` self-conflict in the panel.
#
# The relay now POSTs /api/agent/intents/withdraw_all on every non-zero
# exit so the orphan is cleaned up before the user retries. These tests
# pin the call sites + best-effort failure handling.


class _FakeAsyncClient:
    """Minimal httpx.AsyncClient stand-in for the cleanup tests."""
    def __init__(self, *, post_response=None, post_raises=None):
        self._post_response = post_response
        self._post_raises = post_raises
        self.posts = []  # [(url, json, headers)]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def post(self, url, *, json=None, headers=None):
        self.posts.append((url, json, headers))
        if self._post_raises is not None:
            raise self._post_raises
        return self._post_response


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


async def _run_with_cleanup_capture(proc, fake_client):
    with patch(
        "mpac_mcp.relay.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=proc),
    ), patch(
        "mpac_mcp.relay._build_mcp_config", return_value="/tmp/fake.json",
    ), patch(
        "mpac_mcp.relay.os.path.exists", return_value=False,
    ), patch(
        "mpac_mcp.relay.httpx.AsyncClient", return_value=fake_client,
    ):
        reply = await handle_chat(_ctx(), "hi")
    return reply


def test_nonzero_exit_calls_cleanup_endpoint():
    proc = FakeProc(returncode=1, stdout_bytes=b"boom", stderr_bytes=b"")
    fake = _FakeAsyncClient(
        post_response=_FakeResponse(
            200, {"withdrawn_intent_ids": ["intent-agent-3-abc"]},
        ),
    )
    reply = asyncio.run(_run_with_cleanup_capture(proc, fake))
    assert "exit 1" in reply
    assert len(fake.posts) == 1
    url, body, headers = fake.posts[0]
    assert url.endswith("/api/agent/intents/withdraw_all")
    assert body == {
        "project_id": 1,
        "reason": "claude_exit_1",
    }
    assert headers["Authorization"] == "Bearer test-token"


def test_successful_run_does_not_call_cleanup():
    proc = FakeProc(returncode=0, stdout_bytes=b"reply", stderr_bytes=b"")
    fake = _FakeAsyncClient(
        post_response=_FakeResponse(200, {"withdrawn_intent_ids": []}),
    )
    reply = asyncio.run(_run_with_cleanup_capture(proc, fake))
    assert reply == "reply"
    assert fake.posts == [], "cleanup must not run on successful exits"


def test_cleanup_failure_does_not_corrupt_user_facing_error():
    # If the web app is down, the cleanup POST will raise; the relay
    # should swallow it and still return the original Claude error to
    # the chat UI.
    proc = FakeProc(returncode=1, stdout_bytes=b"", stderr_bytes=b"oh no")
    fake = _FakeAsyncClient(post_raises=RuntimeError("connection refused"))
    reply = asyncio.run(_run_with_cleanup_capture(proc, fake))
    assert "oh no" in reply
    assert "exit 1" in reply
