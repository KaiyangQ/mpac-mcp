"""
v0.2.12: announce_intent must translate the v0.2.8 race-lock 409 response
into a structured dict so Claude reads it as a normal tool result instead
of crashing the subprocess on httpx.HTTPStatusError.

Pre-0.2.12 behavior: r.raise_for_status() turned 409 into an exception
that propagated out of the MCP tool, which surfaced to Claude as "your
tool call failed" — Claude either retried (defeating the race lock) or
gave up entirely. v0.2.12 returns {"rejected": True, ...} so Claude can
inspect the response shape and call defer_intent per the v0.2.12
system-prompt branches.
"""
from unittest.mock import patch, MagicMock

import httpx
import pytest

from mpac_mcp import relay_tools


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "http://test/api/agent/intents")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}", request=req,
                response=httpx.Response(self.status_code, request=req),
            )


class _FakeSyncClient:
    """Minimal sync httpx.Client stand-in matching _client() interface."""
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.posts: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def post(self, url, *, json=None, headers=None):
        self.posts.append((url, json, headers))
        return self._response


def _patch_client(response: _FakeResponse):
    """Patch both _client and _project_id since relay_tools binds them
    at module level."""
    fake = _FakeSyncClient(response)
    return (
        patch.object(relay_tools, "_client", return_value=fake),
        patch.object(relay_tools, "_project_id", return_value=42),
        fake,
    )


def test_announce_intent_returns_dict_on_409_stale_intent():
    """v0.2.12 contract: 409 STALE_INTENT becomes a structured dict
    (rejected=True), NOT an exception. Claude reads the dict and routes
    into the defer_intent branch per the v0.2.12 system prompt."""
    response = _FakeResponse(
        status_code=409,
        payload={
            "detail": {
                "error_code": "STALE_INTENT",
                "intent_id_attempted": "intent-agent-2-attempted",
                "files": ["notes_app/db.py"],
                "description": "Files ['notes_app/db.py'] are already being "
                               "modified by intent intent-agent-1-xyz",
                "guidance": "Call defer_intent ...",
            }
        },
    )
    p_client, p_pid, _ = _patch_client(response)
    with p_client, p_pid:
        result = relay_tools.announce_intent(
            files=["notes_app/db.py"], objective="add feature",
        )

    assert result.get("rejected") is True
    assert result.get("error_code") == "STALE_INTENT"
    assert result.get("files") == ["notes_app/db.py"]
    assert "intent-agent-1-xyz" in result.get("description", "")
    # Guidance text helps Claude format the user-facing reply.
    assert "defer_intent" in result.get("guidance", "")


def test_announce_intent_returns_normal_dict_on_2xx():
    """Success path unchanged: returns server JSON verbatim, no
    rejected key (the v0.2.8 conflicts field passes through too)."""
    response = _FakeResponse(
        status_code=200,
        payload={
            "intent_id": "intent-agent-1-abc",
            "accepted": True,
            "conflicts": [],
        },
    )
    p_client, p_pid, _ = _patch_client(response)
    with p_client, p_pid:
        result = relay_tools.announce_intent(
            files=["notes_app/db.py"], objective="ok",
        )

    assert result.get("intent_id") == "intent-agent-1-abc"
    assert result.get("accepted") is True
    assert "rejected" not in result


def test_announce_intent_passes_through_same_tick_dependency_breakage_conflicts():
    """v0.2.8 same-tick dependency_breakage warning surface: server
    returns accepted=true with non-empty conflicts. Tool MUST forward
    verbatim so Claude can inspect category/other_display_name. v0.2.13
    additionally adds a `user_action_required` sentinel so the response
    shape is qualitatively different from a clean accept (Claude was
    silently dropping the warning when conflicts looked like metadata —
    2026-04-30 e2e measured 0/1 ⚠️ compliance vs 6/6 in the rejected
    branch which has an equivalent sentinel)."""
    response = _FakeResponse(
        status_code=200,
        payload={
            "intent_id": "intent-agent-2-xyz",
            "accepted": True,
            "conflicts": [{
                "conflict_id": "c-1",
                "category": "dependency_breakage",
                "severity": "medium",
                "other_principal_id": "agent:user-1",
                "other_display_name": "Alice's Claude",
                "their_impact_on_us": [
                    {"file": "notes_app/api.py",
                     "symbols": ["notes_app.db.save"]}
                ],
            }],
        },
    )
    p_client, p_pid, _ = _patch_client(response)
    with p_client, p_pid:
        result = relay_tools.announce_intent(
            files=["notes_app/api.py"], objective="add",
        )

    assert result["accepted"] is True
    assert len(result["conflicts"]) == 1
    c = result["conflicts"][0]
    assert c["category"] == "dependency_breakage"
    assert c["other_display_name"] == "Alice's Claude"
    assert c["their_impact_on_us"][0]["symbols"] == ["notes_app.db.save"]
    # v0.2.13 sentinel:
    assert result.get("user_action_required") == \
        "PREFIX_REPLY_WITH_WARNING_AND_NAME_OTHER_PARTY"


def test_announce_intent_clean_accept_does_NOT_get_v0_2_13_sentinel():
    """v0.2.13 only adds the sentinel when there are actual conflicts to
    surface. A clean accept (conflicts: []) must look unchanged so Claude
    doesn't manufacture warnings out of nothing."""
    response = _FakeResponse(
        status_code=200,
        payload={
            "intent_id": "intent-1",
            "accepted": True,
            "conflicts": [],
        },
    )
    p_client, p_pid, _ = _patch_client(response)
    with p_client, p_pid:
        result = relay_tools.announce_intent(files=["x.py"], objective="x")

    assert result.get("conflicts") == []
    assert "user_action_required" not in result


def test_announce_intent_still_raises_on_other_4xx_5xx():
    """Defense: 409 is the ONE special-cased status. Other errors
    (401, 403, 500, ...) should still raise — they're real bugs the
    relay should surface to the user via the standard error path,
    not silently swallow as a structured-rejected dict."""
    response = _FakeResponse(status_code=403)
    p_client, p_pid, _ = _patch_client(response)
    with p_client, p_pid:
        with pytest.raises(httpx.HTTPStatusError):
            relay_tools.announce_intent(
                files=["x.py"], objective="x",
            )
