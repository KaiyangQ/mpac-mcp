"""Claude-as-MPAC-participant agent.

Spawns per chat message: registers Claude as a new participant in the
project's MPAC session, calls the Anthropic API once with a forced
``announce_work`` tool_use to pick files, broadcasts `INTENT_ANNOUNCE`
through the coordinator so other tabs see Claude working, waits a beat
(simulated work), then `INTENT_WITHDRAW` + `GOODBYE` and returns the
user-facing reply text.

Design notes:
* The agent connects through the same ``mpac_bridge.ProjectSession`` as a
  human, using a loopback "send" callback — this makes it a real MPAC
  participant (its messages get broadcast to connected browsers) without
  needing an actual WebSocket.
* Prompt caching is configured on the SYSTEM_PROMPT (bytes frozen, no
  interpolation), so the repeated turns within a project reuse the cached
  prefix.
* If ``ANTHROPIC_API_KEY`` is unset we fall back to a canned reply so the
  agent still performs the MPAC dance (join + announce + withdraw + leave)
  for demo purposes. This makes the Web App usable without an API key.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, CLAUDE_MODEL, IS_PRODUCTION
from ..mpac_bridge import (
    ProjectSession,
    SessionRegistry,
    agent_tokens,
    build_verifier_for_project,
    process_envelope,
    register_and_hello,
    unregister_and_goodbye,
)
from ..models import Project
from .prompts import SYSTEM_PROMPT

log = logging.getLogger("mpac.agent")


# ── Anthropic client (per-user, BYOK) ─────────────────────────────────
#
# Before the semi-public beta we cached a single AsyncAnthropic client at
# module level, keyed off the platform-wide ANTHROPIC_API_KEY. Now each
# request builds its own client from the calling user's stored key
# (decrypted in routes/chat.py and passed in via ClaudeAgent.api_key).
# We don't cache — different users ⇒ different keys ⇒ different clients.
#
# In development (MPAC_WEB_ENV != production) we still honour the legacy
# platform ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN env vars as a fallback,
# so `uvicorn` against a local DB keeps working without a fresh BYOK setup.


def _get_client(user_api_key: str | None):
    """Construct an AsyncAnthropic client for this request.

    Priority: user's BYOK key → dev platform api-key → dev platform bearer.
    In production the platform fallbacks are off (we never read them), so
    a user without a key gets ``None`` and the caller returns a 402.
    """
    try:
        from anthropic import AsyncAnthropic  # noqa: WPS433 — local import is fine
    except ImportError:
        log.warning("anthropic SDK not installed; falling back to canned replies")
        return None

    if user_api_key:
        return AsyncAnthropic(api_key=user_api_key)

    if IS_PRODUCTION:
        # No platform fallback in prod — caller must have provided a key.
        return None

    if ANTHROPIC_API_KEY:
        log.info("Claude agent falling back to dev platform ANTHROPIC_API_KEY")
        return AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    if ANTHROPIC_AUTH_TOKEN:
        log.info("Claude agent falling back to dev platform ANTHROPIC_AUTH_TOKEN")
        return AsyncAnthropic(auth_token=ANTHROPIC_AUTH_TOKEN)
    return None


# ── Tool schema (forced single-call) ─────────────────────────────────

ANNOUNCE_TOOL = {
    "name": "announce_work",
    "description": (
        "Announce the files you plan to edit and the reason. Call this "
        "exactly once before making any change in the shared project."
    ),
    # Field order matters: Claude emits keys in the schema order, so listing
    # ``objective`` + ``files`` before ``summary`` means we can observe which
    # files the agent will touch BEFORE the (long) summary is generated — the
    # streaming path (``_stream_plan_and_announce``) uses this to announce the
    # intent early and hold it exactly as long as Claude takes to finish
    # streaming. No fixed sleep needed.
    "input_schema": {
        "type": "object",
        "properties": {
            "objective": {
                "type": "string",
                "description": (
                    "One-line intent string shown to humans in the collaboration "
                    "panel, e.g. 'refactor verify_token to support refresh tokens'."
                ),
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Files you will touch in THIS turn, relative to the project "
                    "root. Pick from the known file list in the system prompt."
                ),
            },
            "summary": {
                "type": "string",
                "description": (
                    "Multi-paragraph chat reply for the user, explaining what you "
                    "plan to do and sketching the changes. Match the user's "
                    "language (Chinese or English)."
                ),
            },
        },
        "required": ["objective", "files", "summary"],
    },
}


# ── Partial-JSON helpers for streaming early-announce ────────────────

_FILES_KEY = re.compile(r'"files"\s*:\s*')


def _extract_complete_array(partial: str, key_pattern: re.Pattern) -> Optional[list]:
    """If the partial JSON contains a fully-closed array for ``key_pattern``,
    return it. Otherwise ``None``.

    Walks the source character-by-character from the array's opening ``[``,
    tracking string / escape state so commas and brackets inside string
    literals don't fool us.
    """
    m = key_pattern.search(partial)
    if not m:
        return None
    start = m.end()
    if start >= len(partial) or partial[start] != "[":
        return None
    depth = 0
    in_string = False
    escape = False
    for j in range(start, len(partial)):
        ch = partial[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(partial[start:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


_OBJECTIVE_RE = re.compile(r'"objective"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)


def _extract_objective(partial: str) -> Optional[str]:
    """Extract a completed ``objective`` string value from partial JSON."""
    m = _OBJECTIVE_RE.search(partial)
    if not m:
        return None
    try:
        # Re-parse through json.loads to handle escape sequences correctly.
        return json.loads('"' + m.group(1) + '"')
    except json.JSONDecodeError:
        return m.group(1)


# ── The agent itself ─────────────────────────────────────────────────
# (ephemeral agent bearer tokens live in ``mpac_bridge.agent_tokens`` so the
# bridge's verifier closure can see them without a cross-package import.)

class ClaudeAgent:
    """A one-shot Claude MPAC participant.

    Instantiate per chat message; call ``await run(user_message)``; it handles
    the full join → announce → withdraw → leave dance and returns the text
    reply to render in the chat pane.
    """

    def __init__(
        self,
        *,
        project: Project,
        registry: SessionRegistry,
        db,  # SQLAlchemy Session
        api_key: str | None = None,
    ) -> None:
        self.project = project
        self.registry = registry
        self.db = db
        # BYOK: caller (chat route) hands us the decrypted user key.
        self.api_key = api_key

        # Each agent instance (one per chat turn) gets its own principal_id
        # suffix so it doesn't collide with a previous turn's lingering
        # presence (if any). Multiple turns ⇒ multiple distinct Claude
        # entries in Who's Working — fine, they come and go quickly.
        self.principal_id = f"agent:claude:{project.id}:{uuid.uuid4().hex[:6]}"
        self.display_name = "Claude"
        self.roles = ["contributor"]
        self._token = secrets.token_urlsafe(24)

    async def run(self, user_message: str) -> str:
        """Process one chat turn. Returns the assistant reply text.

        Flow (all real, no fixed sleep):

          1. pre-plan: a cheap sniff — we don't know files yet, so we haven't
             announced any intent. Claude is invisible to the session.
          2. JOIN (HELLO → SESSION_INFO) — Claude appears as ``idle``.
          3. STREAM the Anthropic API response:
             - parse partial tool input as it arrives
             - as soon as ``objective`` + ``files`` are complete,
               ``announce_intent`` fires (this is when conflicts can surface)
             - continue streaming; the ``summary`` field takes the bulk of
               the remaining time — this IS the visible "work" window,
               duration == real streaming time, not a fixed sleep
          4. stream ends → ``withdraw_intent`` immediately.
          5. GOODBYE.

        If the Anthropic API isn't available we fall back to a canned plan
        that still does the join / announce / short wait / withdraw dance so
        the MPAC side of the demo keeps working.
        """
        # 1. Ensure session exists + register our ephemeral agent token.
        verifier = build_verifier_for_project(self.db, self.project.id)
        session = await self.registry.get_or_create(
            project_id=self.project.id,
            mpac_session_id=self.project.session_id,
            verifier=verifier,
        )
        agent_tokens.add(self.project.id, self._token)

        async def agent_send(envelope: dict) -> None:
            # Loopback: the agent doesn't actually read inbound events for now.
            # Kept as a no-op so responses addressed back to us don't blow up.
            return None

        # 2. JOIN — visible in panel as "Claude AI · idle".
        conn = await register_and_hello(
            session,
            principal_id=self.principal_id,
            principal_type="agent",
            display_name=self.display_name,
            roles=self.roles,
            credential_value=self._token,
            send=agent_send,
            is_agent=True,
        )
        if conn is None:
            agent_tokens.remove(self.project.id, self._token)
            return (
                "⚠️ Claude couldn't join the MPAC session. Check server logs — "
                "the project's verifier may have rejected the agent token."
            )

        from mpac_protocol.core.models import Scope
        from ..mpac_bridge import build_file_scope

        client = _get_client(self.api_key)
        if client is None:
            # Fallback path: no API key → use canned plan. Keep the announce /
            # withdraw dance so the collaboration panel still demos.
            plan = self._canned_plan(user_message)
            intent_id = f"intent-{uuid.uuid4().hex[:8]}"
            try:
                announce = conn.participant.announce_intent(
                    session_id=session.mpac_session_id,
                    intent_id=intent_id,
                    objective=plan["objective"],
                    scope=build_file_scope(
                        plan["files"], db=self.db, project_id=self.project.id,
                    ),
                )
                await process_envelope(session, announce, self.principal_id)
                # Small, single-purpose visibility window for the canned path:
                # no real work is happening, so ~2s lets the UI paint the
                # announcement before we tear it down.
                await asyncio.sleep(2.0)
                withdraw = conn.participant.withdraw_intent(
                    session_id=session.mpac_session_id,
                    intent_id=intent_id,
                    reason="work_complete",
                )
                await process_envelope(session, withdraw, self.principal_id)
                return plan["summary"]
            finally:
                await unregister_and_goodbye(session, conn)
                agent_tokens.remove(self.project.id, self._token)

        # 3. STREAM path — real API.
        intent_id = f"intent-{uuid.uuid4().hex[:8]}"
        try:
            plan = await self._stream_plan_and_announce(
                client=client,
                conn=conn,
                session=session,
                intent_id=intent_id,
                user_message=user_message,
            )

            # 4. Stream is done → withdraw immediately.
            if plan.get("announced"):
                withdraw = conn.participant.withdraw_intent(
                    session_id=session.mpac_session_id,
                    intent_id=intent_id,
                    reason="work_complete",
                )
                await process_envelope(session, withdraw, self.principal_id)

            return plan["summary"]
        finally:
            # 5. GOODBYE regardless of happy-path / error.
            await unregister_and_goodbye(session, conn)
            agent_tokens.remove(self.project.id, self._token)

    # ── Streaming Anthropic call with early announce ─────────────

    async def _stream_plan_and_announce(
        self,
        *,
        client,
        conn,
        session,
        intent_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """Stream the Anthropic response. Announce intent as soon as the
        ``files`` array is fully emitted (which happens well before the
        summary finishes generating). Returns ``{summary, announced}``.

        Ties the intent-visible duration to real streaming latency — there
        is no fixed sleep. If the summary streams fast, the visible window
        is short; if it takes 10s to generate, it's 10s. No hardcoded wait.
        """
        from mpac_protocol.core.models import Scope
        from ..mpac_bridge import build_file_scope

        system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
        ]

        accumulated_input = ""
        announced = False

        try:
            async with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=2048,
                system=system_blocks,
                tools=[ANNOUNCE_TOOL],
                tool_choice={"type": "tool", "name": "announce_work"},
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for event in stream:
                    # Only tool-input deltas are interesting for early announce.
                    etype = getattr(event, "type", None)
                    if etype != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) != "input_json_delta":
                        continue
                    partial = getattr(delta, "partial_json", "") or ""
                    accumulated_input += partial

                    if announced:
                        continue

                    # Schema order is objective → files → summary.
                    objective = _extract_objective(accumulated_input)
                    files = _extract_complete_array(
                        accumulated_input, _FILES_KEY,
                    )
                    if objective and files:
                        # Normalize + defensively fall back if Claude returned
                        # nothing sensible.
                        files_norm = [str(p) for p in files if p]
                        if not files_norm:
                            continue
                        announce = conn.participant.announce_intent(
                            session_id=session.mpac_session_id,
                            intent_id=intent_id,
                            objective=objective[:200],
                            scope=build_file_scope(
                                files_norm,
                                db=self.db,
                                project_id=self.project.id,
                            ),
                        )
                        await process_envelope(
                            session, announce, self.principal_id,
                        )
                        announced = True
                        log.info(
                            "Claude announced intent early principal_id=%s "
                            "files=%s", self.principal_id, files_norm,
                        )

                final = await stream.get_final_message()
        except Exception as e:
            log.exception("Claude streaming call failed: %s", e)
            canned = self._canned_plan(user_message)
            canned["announced"] = False
            canned["summary"] = (
                f"⚠️ Claude API failed ({type(e).__name__}). Falling back "
                f"to a heuristic plan.\n\n{canned['summary']}"
            )
            return canned

        # Pull the final fully-parsed tool input — that has the summary.
        plan = self._canned_plan(user_message)
        plan["announced"] = announced
        for block in final.content:
            if getattr(block, "type", None) == "tool_use":
                raw = block.input or {}
                files = [str(p) for p in raw.get("files", []) if p]
                plan["summary"] = str(raw.get("summary") or plan["summary"])
                if files and not announced:
                    # Safety net: if streaming parser missed the early
                    # window (shouldn't happen with forced tool_choice),
                    # announce now anyway so MPAC doesn't miss the beat.
                    announce = conn.participant.announce_intent(
                        session_id=session.mpac_session_id,
                        intent_id=intent_id,
                        objective=str(raw.get("objective") or "editing"),
                        scope=build_file_scope(
                            files, db=self.db, project_id=self.project.id,
                        ),
                    )
                    await process_envelope(
                        session, announce, self.principal_id,
                    )
                    plan["announced"] = True
                break
        return plan

    # ── Fallback when API key is missing or API call fails ──────

    def _canned_plan(self, user_message: str) -> Dict[str, Any]:
        """Heuristic file picker + canned reply for demos without an API key.

        The demo story still works — Claude joins, announces, withdraws —
        the only difference is the reply text.
        """
        msg_lower = user_message.lower()
        if any(k in msg_lower for k in ("auth", "login", "jwt", "token",
                                          "用户", "登录", "验证")):
            files = ["src/auth.py"]
            objective = "review and refactor verify_token"
        elif any(k in msg_lower for k in ("api", "endpoint", "route",
                                            "接口", "路由")):
            files = ["src/api.py"]
            objective = "review REST endpoints"
        elif any(k in msg_lower for k in ("test", "测试")):
            files = ["tests/test_auth.py"]
            objective = "review test coverage"
        elif any(k in msg_lower for k in ("readme", "doc", "文档")):
            files = ["README.md"]
            objective = "update documentation"
        else:
            files = ["src/utils/helpers.py"]
            objective = "review helper utilities"

        looks_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in user_message)
        if looks_chinese:
            summary = (
                f"收到。我会先查看 `{files[0]}`，理解当前实现后给出修改建议。\n\n"
                "> ⚠️ 当前服务器未配置 `ANTHROPIC_API_KEY`，所以这条回复是 "
                "fallback 文案。但我已经作为 MPAC participant 加入了这个 "
                "session — 你应该能在右上角的协作面板看到我正在工作的状态。"
            )
        else:
            summary = (
                f"Got it. I'll start by reviewing `{files[0]}` to understand "
                "the current implementation before proposing changes.\n\n"
                "> ⚠️ This server has no `ANTHROPIC_API_KEY` configured, so "
                "this reply is canned. But I **did** join the MPAC session — "
                "check the collaboration panel, you should see me as an active "
                "participant for a few seconds."
            )
        return {"files": files, "objective": objective, "summary": summary}

