"""
Smoke test that the relay system prompt keeps the strong yield/defer_intent
guidance added in v0.2.10.

Background: in v0.2.9 the prompt said "if you decide to YIELD, call
defer_intent" — but when the user's prompt said "just back off, do nothing,"
Claude would interpret "do nothing" literally and skip defer_intent too,
so the Conflicts panel showed no yield-chip even though Claude had
clearly yielded in chat. v0.2.10 strengthens the wording: defer_intent
is part of yielding, not part of doing; "do nothing" never means "skip
defer_intent."

These tests pin a few key phrases so a future refactor of the prompt
doesn't accidentally regress that lesson.
"""

from mpac_mcp.relay import _SYSTEM_PROMPT


def test_prompt_says_defer_intent_is_mandatory_on_yield():
    # The bare word "MUST" + the tool name in the same sentence is the
    # signal Claude needs to override a user prompt that says "do nothing."
    assert "you MUST call **defer_intent" in _SYSTEM_PROMPT


def test_prompt_explicitly_calls_chat_only_yield_a_protocol_violation():
    # Direct anti-pattern callout: "saying I yielded in chat without
    # calling defer_intent is a protocol violation." This phrasing is
    # what makes Claude self-correct mid-turn rather than chat-and-stop.
    assert "protocol violation" in _SYSTEM_PROMPT
    assert "without calling defer_intent" in _SYSTEM_PROMPT


def test_prompt_disambiguates_do_nothing_from_skip_defer_intent():
    # The exact failure mode from case 4 round 1: user says "什么都不要做"
    # and Claude over-interprets it. The prompt must explicitly carve out
    # defer_intent from "doing."
    assert "什么都不要做" in _SYSTEM_PROMPT
    assert "do nothing" in _SYSTEM_PROMPT.lower()
    assert "defer_intent is part of yielding, not part of doing" in _SYSTEM_PROMPT


def test_prompt_still_mentions_yield_branch_skips_announce():
    # Don't regress the "in the yield branch, do NOT call announce_intent"
    # rule — without it Claude sometimes does both (defer + announce),
    # which creates a self-conflict (own intent overlaps own deferred files).
    assert "Do NOT call announce_intent" in _SYSTEM_PROMPT
