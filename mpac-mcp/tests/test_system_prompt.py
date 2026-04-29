"""
Smoke test that the relay system prompt keeps the conflict-handling
defaults that v0.2.10 + v0.2.11 baked in.

History:
* v0.2.10 — added strong "you MUST call defer_intent on yield" + the
  "什么都不要做 ≠ skip defer_intent" carve-out.
* v0.2.11 — split the default behavior by `category`:
    - `scope_overlap` (same file) → default YIELD (almost always a real
      conflict)
    - `dependency_breakage` (cross-file dependency) → default PROCEED
      with a prominent ⚠️ warning (often backward-compatible; yielding
      every spoke when a hub gets touched would kill collaboration).
  This matches `git`'s split between merge conflicts (must resolve)
  and semantic conflicts (warn, leave to type checker / CI / reviewer).

These tests pin key phrases so future refactors don't regress these
lessons. They are intentionally specific to the wording — the wording
IS the contract with the LLM.
"""

from mpac_mcp.relay import _SYSTEM_PROMPT


# ── v0.2.10 lessons (still apply to the scope_overlap branch) ────────


def test_prompt_says_defer_intent_is_mandatory_on_scope_overlap():
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


def test_prompt_says_yield_branch_skips_announce():
    # Don't regress the "in the yield branch, do NOT call announce_intent"
    # rule — without it Claude sometimes does both (defer + announce),
    # which creates a self-conflict (own intent overlaps own deferred files).
    assert "Do NOT call announce_intent" in _SYSTEM_PROMPT


# ── v0.2.11 lessons (category-split defaults) ────────────────────────


def test_prompt_distinguishes_scope_overlap_from_dependency_breakage():
    # Both category names must appear in the prompt — Claude has to know
    # to read the `category` field on each check_overlap entry and dispatch
    # on it.
    assert "scope_overlap" in _SYSTEM_PROMPT
    assert "dependency_breakage" in _SYSTEM_PROMPT


def test_prompt_makes_default_explicit_per_category():
    # Pin the exact "default YIELD" / "default PROCEED" wording so that a
    # future prompt rewrite that softens these ("consider yielding",
    # "you might proceed") gets caught.
    assert "default YIELD" in _SYSTEM_PROMPT
    assert "default PROCEED" in _SYSTEM_PROMPT


def test_prompt_provides_dependency_breakage_warning_template():
    # When proceeding past a dependency_breakage, Claude must START its
    # reply with a visible warning (⚠️ marker is part of the contract so
    # the user can spot it in chat and override).
    assert "⚠️" in _SYSTEM_PROMPT
    # The override phrase the user can use to flip dependency_breakage
    # back to yield, in both English and Chinese, must be advertised so
    # Claude tells the user what to say.
    assert "wait for" in _SYSTEM_PROMPT
    assert "让路" in _SYSTEM_PROMPT


def test_prompt_advertises_proceed_anyway_override_for_scope_overlap():
    # Symmetric override: user can flip scope_overlap from yield → proceed.
    # Without advertising the phrase, the user has no way to know how to
    # ask Claude to ignore the conflict.
    assert "proceed anyway" in _SYSTEM_PROMPT
    assert "硬上" in _SYSTEM_PROMPT


def test_prompt_dependency_breakage_carve_out_is_only_for_pure_dependency():
    # Defense against a subtle prompt regression: if check_overlap returns
    # a mix of scope_overlap AND dependency_breakage entries, the default
    # MUST be yield (the scope_overlap part wins), not proceed. Pin the
    # "ONLY dependency_breakage, no scope_overlap mixed in" phrasing.
    assert "ONLY dependency_breakage" in _SYSTEM_PROMPT
    assert "no scope_overlap mixed in" in _SYSTEM_PROMPT


# ── v0.2.12 lessons (announce_intent response branching) ─────────────


def test_prompt_handles_announce_rejected_branch():
    # v0.2.12 added the "announce came back rejected by the v0.2.8 race
    # lock" branch — without prompting Claude on that response shape, the
    # tool returns {"rejected": true, ...} and Claude either ignores it
    # or hallucinates a retry, both of which break the race lock's UX.
    assert "STALE_INTENT" in _SYSTEM_PROMPT
    assert '"rejected": true' in _SYSTEM_PROMPT or "rejected: true" in _SYSTEM_PROMPT
    assert "DO NOT retry the announce" in _SYSTEM_PROMPT


def test_prompt_handles_announce_with_same_tick_conflicts_branch():
    # v0.2.12 also added the "announce went through but had a same-tick
    # dependency_breakage" branch — covers the race window where
    # check_overlap was clean but a peer's announce arrived between
    # check and announce. Should continue + ⚠️ warning.
    assert "same-tick dependency_breakage" in _SYSTEM_PROMPT
    assert "conflicts` is " in _SYSTEM_PROMPT  # "conflicts is non-empty"
    # Both branch outcomes mention the v0.2.11 ⚠️ template — the
    # warning template is reused, not duplicated. Just ensure the
    # warning emoji appears somewhere in the prompt.
    assert "⚠️" in _SYSTEM_PROMPT
