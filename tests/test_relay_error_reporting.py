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


# ── 2026-04-29: cross-turn session continuity (v0.2.8) ────────────────
#
# `--output-format json` makes claude -p emit
# `{"session_id": "...", "result": "..."}` on stdout. The relay parses
# this, captures session_id, and passes `--resume <id>` on the next
# invocation so Claude has full conversation memory across turns.


import json as _json
import mpac_mcp.relay as _relay


def _reset_session():
    _relay._session_id = None


def test_json_output_extracts_session_id_and_result():
    _reset_session()
    payload = _json.dumps({
        "session_id": "abc-123-uuid",
        "result": "Hi there!",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    }).encode("utf-8")
    proc = FakeProc(returncode=0, stdout_bytes=payload, stderr_bytes=b"")
    reply = asyncio.run(_run(proc))
    assert reply == "Hi there!"
    assert _relay._session_id == "abc-123-uuid"


def test_session_id_passed_as_resume_on_second_call():
    _reset_session()
    # Turn 1: session_id captured.
    payload_1 = _json.dumps({
        "session_id": "uuid-1",
        "result": "first reply",
    }).encode("utf-8")
    captured_argv = []

    async def fake_subprocess_exec(*argv, **kwargs):
        captured_argv.append(argv)
        # Return the same FakeProc each call (with payload_1 stdout).
        return FakeProc(returncode=0, stdout_bytes=payload_1, stderr_bytes=b"")

    with patch(
        "mpac_mcp.relay.asyncio.create_subprocess_exec",
        new=fake_subprocess_exec,
    ), patch(
        "mpac_mcp.relay._build_mcp_config", return_value="/tmp/fake.json",
    ), patch(
        "mpac_mcp.relay.os.path.exists", return_value=False,
    ):
        asyncio.run(handle_chat(_ctx(), "first"))
        asyncio.run(handle_chat(_ctx(), "second"))

    assert len(captured_argv) == 2
    # Turn 1: NO --resume in argv.
    assert "--resume" not in captured_argv[0], (
        "first turn should not include --resume — there's nothing to resume"
    )
    # Turn 2: --resume <captured uuid>.
    assert "--resume" in captured_argv[1]
    idx = captured_argv[1].index("--resume")
    assert captured_argv[1][idx + 1] == "uuid-1"


def test_non_json_stdout_falls_back_to_raw_reply():
    # If a future Claude Code version regresses the JSON output schema,
    # don't drop the user's reply on the floor — surface raw stdout.
    _reset_session()
    proc = FakeProc(
        returncode=0,
        stdout_bytes=b"plain text reply, not JSON",
        stderr_bytes=b"",
    )
    reply = asyncio.run(_run(proc))
    assert reply == "plain text reply, not JSON"
    # Session id should remain None — we couldn't parse it.
    assert _relay._session_id is None


def test_session_id_updates_when_claude_returns_different_one():
    # Claude Code falls back to a fresh session if --resume <id> is
    # invalid/expired. We capture the new session_id silently so the
    # next turn resumes the new one, not the dead one.
    _reset_session()
    _relay._session_id = "stale-uuid"
    payload = _json.dumps({
        "session_id": "fresh-uuid",
        "result": "ok",
    }).encode("utf-8")
    proc = FakeProc(returncode=0, stdout_bytes=payload, stderr_bytes=b"")
    asyncio.run(_run(proc))
    assert _relay._session_id == "fresh-uuid"


def test_argv_includes_output_format_json():
    _reset_session()
    captured_argv = []

    async def fake_subprocess_exec(*argv, **kwargs):
        captured_argv.append(argv)
        return FakeProc(returncode=0, stdout_bytes=b'{"session_id":"x","result":"hi"}', stderr_bytes=b"")

    with patch(
        "mpac_mcp.relay.asyncio.create_subprocess_exec",
        new=fake_subprocess_exec,
    ), patch(
        "mpac_mcp.relay._build_mcp_config", return_value="/tmp/fake.json",
    ), patch(
        "mpac_mcp.relay.os.path.exists", return_value=False,
    ):
        asyncio.run(handle_chat(_ctx(), "hi"))

    assert "--output-format" in captured_argv[0]
    idx = captured_argv[0].index("--output-format")
    assert captured_argv[0][idx + 1] == "json"


# ─── reset_to_seed → drop resumed session ──────────────────────────────


def test_drop_session_for_reset_clears_session_id():
    """The reset_to_seed PROJECT_EVENT handler must clear ``_session_id``
    so the next ``claude -p`` turn starts fresh — otherwise Claude resumes
    a conversation that believes in pre-reset file state."""
    _relay._session_id = "stale-uuid"
    asyncio.run(_relay._drop_session_for_reset())
    assert _relay._session_id is None


def test_drop_session_for_reset_is_noop_when_no_session():
    """First-turn relay (no session yet) should still tolerate the reset
    event without error."""
    _relay._session_id = None
    asyncio.run(_relay._drop_session_for_reset())
    assert _relay._session_id is None


def test_drop_session_for_reset_serializes_with_in_flight_chat():
    """If a chat is mid-flight when reset_to_seed arrives, the reset must
    wait for the in-flight turn to finish (and write its session_id)
    before clearing — otherwise the chat's post-completion write at the
    end of ``_handle_chat_locked`` re-pollutes the cleared state."""
    _relay._session_id = None

    captured_session_during_clear = []

    async def slow_subprocess(*argv, **kwargs):
        # In-flight chat takes time → makes the reset's lock acquisition
        # block until this turn completes.
        await asyncio.sleep(0.05)
        return FakeProc(
            returncode=0,
            stdout_bytes=b'{"session_id":"new-uuid","result":"ok"}',
            stderr_bytes=b"",
        )

    async def scenario():
        with patch(
            "mpac_mcp.relay.asyncio.create_subprocess_exec",
            new=slow_subprocess,
        ), patch(
            "mpac_mcp.relay._build_mcp_config", return_value="/tmp/fake.json",
        ), patch(
            "mpac_mcp.relay.os.path.exists", return_value=False,
        ):
            chat_task = asyncio.create_task(handle_chat(_ctx(), "hi"))
            # Let the chat acquire the lock first.
            await asyncio.sleep(0.01)
            reset_task = asyncio.create_task(_relay._drop_session_for_reset())
            await chat_task
            await reset_task
            captured_session_during_clear.append(_relay._session_id)

    asyncio.run(scenario())
    # After both finish: session must be cleared, not the chat's "new-uuid".
    assert captured_session_during_clear == [None]
