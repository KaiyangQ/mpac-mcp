"""mpac-mcp-relay — local Claude Code bridge for MPAC web app.

Run this on your laptop after clicking "Connect Claude" in the web app:

    mpac-mcp-relay \\
        --project-url ws://127.0.0.1:8001/ws/relay/1 \\
        --token mpac_agent_xxxxxxxx

What it does
------------
Opens a single WebSocket to the web app. The web app:
  1. Registers this process as an MPAC participant in the project's session,
     so you show up as "<your-name>'s Claude" in WHO'S WORKING on every
     connected browser.
  2. When a human user on that project types in the in-browser AI chat,
     forwards the message to this relay. We spawn `claude -p` locally
     (using your Claude Code subscription — no API key needed) and send
     the reply back.

Protocol (JSON frames):
  Server → us:  {"type":"chat", "message_id":..., "message":"..."}
  us → Server:  {"type":"chat_reply", "message_id":..., "reply":"..."}
  us → Server:  {"type":"hello", "version":"0.1.0"}  (sent once after connect)

MCP tools (Milestone B)
-----------------------
Each `claude -p` spawn injects a temp MCP config pointing at the
``mpac_mcp.relay_tools`` stdio server. That server exposes six tools
(list_project_files, read_project_file, write_project_file,
check_overlap, announce_intent, withdraw_intent) which Claude can call
to actually read and edit the shared project files + participate in
the MPAC session.

MCP_CONNECTION_BLOCKING=1 is mandatory: headless `claude -p` loads MCP
servers asynchronously by default and silently drops their tools before
Claude's first turn — verified on 2026-04-18. Blocking mode waits for
the tools/list RPC before sending the prompt.

--dangerously-skip-permissions is used because the agent has no human at
a terminal to approve each tool call. Safety is scoped by the agent
token: it only has access to this one project.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx
import websockets


log = logging.getLogger("mpac.relay")

RELAY_VERSION = "0.1.0"
CLAUDE_TIMEOUT_SEC = 180.0  # Milestone B: Claude using MCP tools takes longer


# ── Argparse ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mpac-mcp-relay",
        description="Local Claude Code bridge for the MPAC web app.",
    )
    p.add_argument(
        "--project-url", required=True,
        help="WebSocket URL, e.g. ws://127.0.0.1:8001/ws/relay/1",
    )
    p.add_argument(
        "--token", required=True,
        help="Agent bearer token from the web app's 'Connect Claude' modal.",
    )
    p.add_argument(
        "--claude-binary", default=None,
        help="Path to the claude CLI (default: auto-detect via $PATH).",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose logging.",
    )
    return p


# ── Chat handling ───────────────────────────────────────────────────────

@dataclass
class RelayContext:
    claude_binary: str
    project_id: int
    web_http_url: str      # http:// or https:// base for the MCP subprocess
    agent_token: str       # bearer token for the web app


_SYSTEM_PROMPT = (
    "You are the AI participant of a human↔agent coding session coordinated "
    "by MPAC (Multi-Principal Agent Coordination).\n\n"
    "CRITICAL: The 'project' the user is talking about is a SHARED virtual "
    "workspace stored in a web app, NOT your local filesystem. You CANNOT "
    "see it through your usual Read/Glob/Bash/LS tools — those have been "
    "disabled. The ONLY way to interact with this project's files is via "
    "the `mpac-coding` MCP server tools:\n"
    "  - list_project_files()\n"
    "  - read_project_file(path)\n"
    "  - write_project_file(path, content)\n"
    "  - check_overlap(files)\n"
    "  - announce_intent(files, objective) → returns intent_id\n"
    "  - withdraw_intent(intent_id, reason)\n"
    "  - list_my_active_intents()              ← v0.2.7, see below\n"
    "  - withdraw_all_my_intents(reason)       ← v0.2.7, see below\n"
    "  - defer_intent(files, reason, observed_intent_ids)  ← v0.2.9, see below\n\n"
    "When the user asks about ANY file (e.g. `src/api.py`, `README.md`), "
    "assume they mean a file inside the shared project. Do NOT say it "
    "doesn't exist until you've checked with list_project_files() or "
    "read_project_file().\n\n"
    "MEMORY MODEL — you HAVE memory of prior turns within the current "
    "session: the relay resumes the conversation, so you can see what "
    "you said and did in earlier turns. The session resets only when "
    "the project is reset to seed (file state wiped) — at that point "
    "everything you remember from before the reset is moot, since the "
    "files you read no longer exist. Two implications:\n"
    "  * If a prior-turn intent_id is still relevant, you may use it "
    "directly. But if you're unsure whether the project state has "
    "drifted (e.g. user took a long break, or another participant "
    "may have moved on), call list_my_active_intents() to verify "
    "before relying on a remembered id — your memory is of YOUR past "
    "actions, not of the current coordinator state.\n"
    "  * After a project reset, do NOT cite work you remember doing "
    "in pre-reset turns; those files are gone. Treat the next turn as "
    "a fresh project.\n\n"
    "Protocol when editing files:\n"
    "  1. If uncertain what's in the project, call list_project_files first.\n"
    "  2. BEFORE editing, call check_overlap(files). Each returned entry "
    "has a `category` field — `scope_overlap` (same file, almost always "
    "a real conflict) vs `dependency_breakage` (cross-file dependency, "
    "often backward-compatible like adding kwargs or new methods). Treat "
    "the two categories DIFFERENTLY:\n"
    "\n"
    "     * **`scope_overlap` entries — default YIELD.** Same-file "
    "overlap means whoever finishes second overwrites the first; this "
    "is almost always a real conflict. you MUST call "
    "**defer_intent(files, observed_intent_ids=[...])** with the "
    "intent_ids you saw, then reply to the user: \"{other} is editing "
    "the same file ({files}). I yielded — say 'proceed anyway' / "
    "'硬上' if you want me to continue despite the conflict.\" Do NOT "
    "call announce_intent in this branch. The phrases 'do nothing' / "
    "'don't do anything' / '什么都不要做' from the user mean 'don't "
    "ANNOUNCE or WRITE' — they NEVER mean 'skip defer_intent'; "
    "defer_intent is part of yielding, not part of doing. Saying "
    "'I'm yielding' / '我让路了' in chat without calling defer_intent "
    "is a protocol violation.\n"
    "\n"
    "     * **`dependency_breakage` entries (and ONLY "
    "dependency_breakage, no scope_overlap mixed in) — default "
    "PROCEED with mandatory situational-awareness disclosure.** "
    "Cross-file dependencies are often backward-compatible. Don't "
    "yield by default — that would force every spoke to wait whenever "
    "a hub file is touched, killing the collaboration system. Instead, "
    "in your reply to the user, START with a mandatory disclosure: "
    "\"⚠️ {other} is also editing related code: changing `{symbol}` "
    "in {their_file}, which my work in {your_file} uses.\" After that "
    "header you MAY add your own assessment (e.g. \"This looks "
    "backward-compatible so should be fine\" or \"Their signature "
    "change may break my caller — you may want to wait for them\"), "
    "and you MAY mention the override phrase \"'wait for {other}' / "
    "'让路'\". But **the ⚠️ HEADER ITSELF IS MANDATORY regardless of "
    "your judgment about safety**. The disclosure is not a danger "
    "warning, it is a parallel-work notification — the user needs "
    "visibility on cross-file edits in dependency chains so they can "
    "make their own coordination call. Your job is to surface, theirs "
    "is to decide. Then continue with announce_intent + write.\n"
    "\n"
    "     * **User overrides in their next message:**\n"
    "       - 'proceed anyway' / 'ignore conflict' / '硬上' / '我知道有"
    "冲突，继续' → skip defer_intent, continue to step 3 even for "
    "scope_overlap.\n"
    "       - 'wait for X' / 'let X finish' / '让路' / '等他完成' → "
    "call defer_intent immediately even for dependency_breakage; do "
    "not announce or write.\n"
    "\n"
    "     * **If check_overlap returns empty:** proceed normally to "
    "step 3.\n"
    "  3. Call announce_intent(files, objective) BEFORE the first write. "
    "Remember the returned intent_id within THIS turn. **Inspect the "
    "response shape — v0.2.8+ announce can come back with race-lock "
    "rejections or same-tick conflict warnings even if your earlier "
    "check_overlap was clean** (the other party announced in the "
    "milliseconds between your check and your announce):\n"
    "\n"
    "     * **If response has `\"rejected\": true` and "
    "`error_code: STALE_INTENT`** → another principal claimed this "
    "file in the race window. DO NOT retry the announce. Call "
    "**defer_intent(files=..., observed_intent_ids=[...])** "
    "(use intent_ids from check_overlap if you have them; if not, "
    "call check_overlap NOW to fetch them) and reply to the user: "
    "\"Another participant just claimed {files} ({description}). "
    "I yielded — say 'proceed anyway' / '硬上' to retry once they "
    "withdraw.\" Do NOT write files in this branch.\n"
    "\n"
    "     * **If response has `accepted: true` AND "
    "`must_surface_to_user: true`** (v0.2.14+) → coordinator detected "
    "a same-tick dependency_breakage with another live intent. The "
    "response has THREE directive fields you MUST execute:\n"
    "         - `surface_warning_text` — a fully-formed ⚠️ string, "
    "ready to use\n"
    "         - `guidance` — text instruction (mirrors the rejected "
    "branch's guidance field)\n"
    "         - `must_surface_to_user: true` — top-level boolean "
    "saying \"this response is a directive, not just metadata\"\n"
    "       **Action: COPY `surface_warning_text` verbatim as the "
    "FIRST line of your reply, then write the rest of your reply "
    "(work summary + any backward-compat analysis you want to add).** "
    "Treat this exactly like the `guidance` field on the rejected "
    "branch — it's an instruction, not optional advice. The "
    "verbatim-copy form removes any chance of you paraphrasing the "
    "warning into something less visible.\n"
    "\n"
    "       **v0.2.14 anti-pattern callout** — DO NOT skip the "
    "verbatim copy because you decide your change \"looks backward "
    "compatible\" (e.g. you're adding a kwarg with a default, or "
    "adding a new method, or only tightening internal behavior). "
    "Backward-compat assessment is your POST-disclosure analysis, "
    "not a substitute for the disclosure. The user wants to know "
    "that two agents are touching code in the same dependency chain "
    "regardless of whether you think the interaction is safe. Your "
    "judgment can be wrong: you might miss a return-type change, an "
    "exception-type change, or a side-effect change that the "
    "dependent code happens to rely on. The user has more context "
    "than you about what their teammate cares about. Surface first, "
    "judge after.\n"
    "\n"
    "       Then continue to step 4 (write the files). The user can "
    "override with 'wait for X' / '让路' to make you withdraw + defer.\n"
    "\n"
    "       (Legacy: pre-v0.2.14 servers may return only `conflicts: "
    "[...]` + `user_action_required: PREFIX_REPLY_...` without the "
    "v0.2.14 directive fields. In that case, construct the ⚠️ "
    "yourself: \"⚠️ {conflicts[0].other_display_name} is also "
    "editing related code: changing `{symbols[0]}` in "
    "{their_impact_on_us[0].file}, which my work in {your_file} "
    "uses.\")\n"
    "\n"
    "     * **If response has `accepted: true` AND `conflicts: []`** "
    "→ clean accept, continue normally.\n"
    "  4. For each file: read_project_file → decide change → write_project_file "
    "with the FULL new content (these tools don't support diffs).\n"
    "  5. When done, call withdraw_intent(intent_id) within the SAME turn. "
    "If you've lost the id (e.g. user is asking you to clean up from an "
    "earlier turn), call list_my_active_intents() to recover the id list, "
    "then withdraw_intent on each — or call withdraw_all_my_intents() to "
    "drop everything in one shot. Don't leave dangling intents.\n\n"
    "If the user says 'withdraw' / 'release' / 'cancel' / 'stop' / "
    "'撤回' / '取消' your intent, do NOT just reply 'done' — actually call "
    "an MCP tool. If you have the intent_id from this turn (or a still-"
    "valid one from a prior turn in the same session), use "
    "withdraw_intent. If you can't find a usable id, "
    "call withdraw_all_my_intents(reason='user_requested').\n\n"
    "**v0.2.13 — POST-DEFER OVERRIDE RETRY RULE.** When the user says "
    "'proceed anyway' / 'ignore conflict' / '硬上' / '继续' / '再试一次' "
    "AND your prior-turn context shows you previously got a STALE_INTENT "
    "rejection + called defer_intent, you MUST re-call announce_intent "
    "FIRST before deciding what to tell the user. The other party's "
    "intent may have withdrawn in the time since your last attempt — "
    "your subprocess receives no reactive event notifications between "
    "turns, so the ONLY way to know the current state is to retry. "
    "NEVER refuse the retry based on a stale prior tool result. "
    "Possible outcomes after the retry:\n"
    "  - Announce succeeds (other party withdrew) → continue to step 4 "
    "(write the files) — do not mention the prior rejection, just do the "
    "work and report success.\n"
    "  - Announce gets rejected again (other party still active) → reply "
    "with the NEW description from this attempt's response, not the old "
    "one; tell the user the other party is still editing and the lock "
    "is still in effect.\n"
    "Retrying on user override is cheap (one HTTP call); refusing to "
    "retry and citing a stale intent_id is the failure mode this rule "
    "exists to prevent.\n\n"
    "If the user only asks a question that doesn't require edits, answer "
    "concisely without announcing an intent. But still use read_project_file "
    "to consult actual file contents when relevant."
)


def _build_mcp_config(ctx: RelayContext) -> str:
    """Write a temp JSON config pointing `claude -p` at our relay_tools MCP
    stdio server, return the file path.

    We launch the server via the SAME Python interpreter this process runs
    on, so whatever mpac-mcp venv the user installed into is guaranteed to
    be on sys.path. No need to chase PYTHONPATH.
    """
    python_exe = sys.executable
    config = {
        "mcpServers": {
            "mpac-coding": {
                "command": python_exe,
                "args": ["-m", "mpac_mcp.relay_tools"],
                "env": {
                    "MPAC_WEB_URL": ctx.web_http_url,
                    "MPAC_AGENT_TOKEN": ctx.agent_token,
                    "MPAC_PROJECT_ID": str(ctx.project_id),
                },
            }
        }
    }
    fd, path = tempfile.mkstemp(prefix="mpac-relay-mcp-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(config, f)
    return path


async def _withdraw_orphan_intents(
    ctx: "RelayContext", reason: str
) -> list[str]:
    """Best-effort: tell the web app to withdraw any intents the just-failed
    subprocess left dangling. The agent token is principal-scoped, so this
    only ever touches THIS relay's own intents in THIS project — the server
    iterates over the coordinator's registry filtered by ``conn.principal_id``.

    Failures are swallowed to a log line: a cleanup failure must not turn a
    chat reply into an exception path. Worst case the orphan stays around,
    which is what we had before this code existed.
    """
    url = f"{ctx.web_http_url}/api/agent/intents/withdraw_all"
    headers = {"Authorization": f"Bearer {ctx.agent_token}"}
    body = {"project_id": ctx.project_id, "reason": reason}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(url, json=body, headers=headers)
            if r.status_code >= 400:
                log.warning(
                    "Orphan-intent cleanup HTTP %s: %s",
                    r.status_code, r.text[:200],
                )
                return []
            data = r.json()
    except Exception as e:
        log.warning("Orphan-intent cleanup call failed: %s", e)
        return []
    return list(data.get("withdrawn_intent_ids") or [])


# ── Cross-turn session continuity (v0.2.8) ─────────────────────────────
#
# Each `claude -p` is one-shot — the subprocess loses every in-memory
# detail when it exits, including any intent_id Claude received. Pre-0.2.8
# this meant a user message in turn N had no idea what happened in turn
# N-1; even with the v0.2.7 list_my_active_intents tool, Claude couldn't
# discuss what it had been doing without re-reading the project from
# scratch.
#
# Claude Code supports `--resume <session_id>` in `-p` mode (verified
# 2026-04-29). With `--output-format json` the first invocation returns
# `{"session_id": "...", "result": "..."}`, which we capture and pass
# back as `--resume` on the next call. Result: full conversation memory
# across turns, including intent_ids, file edits, and prior reasoning.
#
# Concurrency: relay's WS loop currently spawns each chat as
# `asyncio.create_task`, so two messages can race. Without a lock,
# concurrent calls would either both start fresh sessions (no resume,
# session_id flapping) or read a stale id mid-update. We use an
# asyncio.Lock to serialize chats per relay process — one Claude
# subprocess at a time per (user, project). The trade-off is a bursty
# message wait, which is acceptable: the existing claude -p turn already
# takes 5–30s, queuing the next one behind it doesn't change UX much,
# and getting cross-turn memory right is more valuable.
#
# Lock is initialized lazily (asyncio.Lock binds to the running loop).

_chat_lock: Optional[asyncio.Lock] = None
_session_id: Optional[str] = None


def _get_chat_lock() -> asyncio.Lock:
    global _chat_lock
    if _chat_lock is None:
        _chat_lock = asyncio.Lock()
    return _chat_lock


async def _drop_session_for_reset() -> None:
    """Clear the resumed Claude session id so the next ``claude -p`` turn
    starts fresh. Called when the web backend broadcasts a reset_to_seed
    PROJECT_EVENT — the in-memory conversation otherwise still believes
    in files that no longer exist on disk, and Claude routinely says "I
    already added that" and skips the work.

    We acquire the chat lock first so any in-flight turn finishes (and
    writes its session_id) before we clear; otherwise that write races
    our clear and we re-resume the very session we just abandoned.
    """
    global _session_id
    async with _get_chat_lock():
        if _session_id is not None:
            log.info("reset_to_seed: dropping session %s; next turn fresh",
                     _session_id)
            _session_id = None


async def handle_chat(ctx: RelayContext, message: str) -> str:
    """Spawn `claude -p` with MCP_CONNECTION_BLOCKING=1 + the mpac-coding
    MCP server and return its stdout.

    Resumes the per-relay session if one exists, so Claude has full
    memory of prior turns (intent_ids, file edits, reasoning). First call
    starts a fresh session; subsequent calls add `--resume <id>`.

    Errors are caught and returned as a user-facing message so the web app
    chat always gets SOMETHING back — surfacing relay failures in-line is
    more useful than a spinning loader.
    """
    async with _get_chat_lock():
        return await _handle_chat_locked(ctx, message)


async def _handle_chat_locked(ctx: RelayContext, message: str) -> str:
    global _session_id
    env = os.environ.copy()
    env["MCP_CONNECTION_BLOCKING"] = "1"
    # Neutralize any API keys that might be hanging around — we explicitly
    # want the subscription path here. If the user has ANTHROPIC_API_KEY
    # set Claude Code would prefer it over the OAuth credential.
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)

    mcp_config_path: Optional[str] = None
    try:
        mcp_config_path = _build_mcp_config(ctx)
        # Build argv. Two new flags compared to pre-0.2.8:
        #   * --output-format json  — required to capture session_id from
        #     stdout (default text format only emits the assistant reply).
        #   * --resume <id>          — only added on turn 2+, when we already
        #     have a session_id from the previous turn.
        # Ordering: flags before any positional args. Claude Code's argparser
        # is forgiving but we keep --resume immediately after --strict-mcp-config
        # for readability in stack traces.
        argv = [
            ctx.claude_binary, "-p",
            "--output-format", "json",
            "--mcp-config", mcp_config_path,
            "--strict-mcp-config",
            # Block Claude's built-in filesystem tools — the "project" is
            # the web app's virtual FS behind MCP, NOT the relay's cwd.
            # IMPORTANT: `--tools ""` disables ALL tools including MCP,
            # which made Claude hallucinate fake <tool_call> tags in its
            # reply. Using --disallowedTools with specific names keeps
            # MCP tools enabled while blocking local-FS access.
            "--disallowedTools",
            "Read", "Edit", "Write", "Bash", "Glob", "Grep", "NotebookEdit",
            "--dangerously-skip-permissions",
            "--append-system-prompt", _SYSTEM_PROMPT,
        ]
        if _session_id is not None:
            argv.extend(["--resume", _session_id])
        log.info(
            "Spawning claude -p (msg len=%d, mcp_config=%s, resume=%s)",
            len(message), mcp_config_path, _session_id or "<new>",
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                # NOTE: `message` is sent via stdin, NOT as a positional argv.
                # On Windows the `claude` CLI is `claude.cmd` (npm shim), so
                # subprocess goes through `cmd.exe /c claude.cmd ...`, and
                # cmd.exe's argv quoting eats user-typed chat messages that
                # contain &, |, %, parens, or embedded newlines — claude then
                # sees `-p` with no positional and bails with "Input must be
                # provided either through stdin or as a prompt argument".
                # Stdin sidesteps cmd.exe's argv parsing entirely; works the
                # same on macOS / Linux. Verified on Windows / Python 3.14.
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=message.encode("utf-8")),
                    timeout=CLAUDE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                # Subprocess died mid-flight; if it had already announced an
                # intent, the orphan would block siblings on the same files
                # forever. Cleanup is async to keep the UX response snappy.
                cleaned = await _withdraw_orphan_intents(ctx, "claude_timeout")
                if cleaned:
                    log.info("Cleaned %d orphan intents after timeout: %s",
                             len(cleaned), cleaned)
                return f"[relay] Claude Code timed out after {CLAUDE_TIMEOUT_SEC:.0f}s"
        except FileNotFoundError:
            return (
                "[relay] `claude` CLI not found on PATH. "
                "Install Claude Code first: "
                "`npm install -g @anthropic-ai/claude-code`"
            )
        except Exception as e:
            log.exception("claude -p spawn failed")
            return f"[relay] Failed to run Claude Code: {e}"

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            out = stdout.decode("utf-8", errors="replace").strip()
            log.warning("claude -p exit=%s stderr=%r stdout=%r",
                        proc.returncode, err[:500], out[:500])
            # The subprocess may have called announce_intent before failing
            # (e.g. it announced, then write_project_file's followup got
            # blocked by the API content filter). Without this cleanup the
            # intent stays ACTIVE forever — every later announce on the
            # same scope from this principal used to surface a "self
            # conflict" until coordinator 2c shipped. Cleanup is still
            # worth doing so siblings don't see a phantom claim either.
            cleaned = await _withdraw_orphan_intents(
                ctx, f"claude_exit_{proc.returncode}",
            )
            if cleaned:
                log.info("Cleaned %d orphan intents after exit %d: %s",
                         len(cleaned), proc.returncode, cleaned)
            # The Claude Code CLI writes several user-facing errors to
            # STDOUT, not stderr — notably "Claude Code on Windows requires
            # git-bash" and "Not logged in · Please run /login". If we
            # only surfaced stderr the user would see "[relay] Claude
            # Code failed (exit 1):" with an empty body — the most
            # frustrating possible UX. Combine both streams; stderr
            # first (convention), stdout second (where the real
            # diagnostic often lives).
            if err and out:
                body = f"{err}\n{out}"
            else:
                body = err or out or "(no output on stderr or stdout)"
            hay = (err + " " + out).lower()
            if "login" in hay or "auth" in hay:
                return (
                    f"[relay] Claude Code isn't authenticated on this machine.\n"
                    f"Run `claude /login` in a terminal, then retry.\n\n"
                    f"Raw error: {body[:400]}"
                )
            return (f"[relay] Claude Code failed "
                    f"(exit {proc.returncode}): {body[:400]}")

        # Success path. With --output-format json, stdout is a JSON object
        # with at least {result, session_id, ...}. Parse it; on failure
        # (a future Claude Code version that breaks the schema, or some
        # weird wrapper) fall back to raw stdout so the user still gets
        # something instead of an empty reply.
        # _session_id is already declared global at the top of this fn.
        raw_stdout = stdout.decode("utf-8", errors="replace")
        try:
            data = json.loads(raw_stdout)
        except (json.JSONDecodeError, ValueError):
            log.warning(
                "claude -p stdout was not JSON despite --output-format json; "
                "treating raw text as reply (session continuity disabled "
                "for this turn). First 200 chars: %r", raw_stdout[:200],
            )
            reply = raw_stdout.rstrip()
            log.info("claude -p completed reply_len=%d (raw)", len(reply))
            return reply or "[relay] Claude returned no output."

        new_session_id = data.get("session_id")
        if new_session_id and new_session_id != _session_id:
            log.info(
                "Session id %s -> %s (resume on next turn)",
                _session_id or "<new>", new_session_id,
            )
            _session_id = new_session_id
        reply = (data.get("result") or "").rstrip()
        log.info("claude -p completed reply_len=%d session=%s",
                 len(reply), _session_id)
        return reply or "[relay] Claude returned no output."
    finally:
        if mcp_config_path and os.path.exists(mcp_config_path):
            try:
                os.unlink(mcp_config_path)
            except OSError:
                pass


# ── WebSocket loop ──────────────────────────────────────────────────────

def _parse_project_url(url: str) -> tuple[int, str]:
    """From a project-url like ``ws://127.0.0.1:8001/ws/relay/1``, return
    ``(project_id, http_base_url)`` — the http_base is used by the
    relay_tools MCP subprocess to call the file + intent APIs.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("ws", "wss"):
        raise ValueError(f"project-url must be ws:// or wss://, got {url!r}")
    # Path should end in /ws/relay/{id}.
    m = re.search(r"/ws/relay/(\d+)/?$", parsed.path)
    if not m:
        raise ValueError(
            f"project-url path must end in /ws/relay/<project_id>, got {parsed.path!r}"
        )
    project_id = int(m.group(1))
    http_scheme = "https" if parsed.scheme == "wss" else "http"
    http_base = f"{http_scheme}://{parsed.netloc}"
    return project_id, http_base


async def run_relay(args: argparse.Namespace) -> int:
    claude_binary = args.claude_binary or shutil.which("claude")
    if not claude_binary:
        print(
            "error: could not find `claude` on PATH. "
            "Install via `npm install -g @anthropic-ai/claude-code` "
            "or pass --claude-binary.",
            file=sys.stderr,
        )
        return 2

    try:
        project_id, web_http_url = _parse_project_url(args.project_url)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    ctx = RelayContext(
        claude_binary=claude_binary,
        project_id=project_id,
        web_http_url=web_http_url,
        agent_token=args.token,
    )

    uri = args.project_url
    log.info("Connecting to %s", uri)

    # Auth via Authorization header instead of ``?token=`` in the URL — keeps
    # the agent bearer out of any access log / proxy log / browser-history
    # surface that records request URLs (web-app v3, 2026-04-25). The web
    # backend's ``/ws/relay`` endpoint accepts BOTH paths during the soft-
    # rollout window: header (preferred) AND query (back-compat for relays
    # built against pre-0.2.5 mpac-mcp). Once we're sure no clients are on
    # the old path, the query fallback can come out.
    #
    # Header-kwarg name compat: the websockets library renamed
    # ``extra_headers`` → ``additional_headers`` in v14. Our pyproject still
    # allows ``websockets>=12.0`` for environments that pinned an older
    # version, so we pick the right kwarg at runtime — same pattern
    # ``coordinator_bridge._WS_HEADER_KWARG`` uses. Hard-coding
    # ``additional_headers=`` would break any user with v12/13 already
    # satisfying the constraint (pip won't upgrade past a satisfied pin).
    auth_headers = [("Authorization", f"Bearer {args.token}")]
    try:
        _ws_major = int(websockets.__version__.split(".")[0])
    except (AttributeError, ValueError):
        _ws_major = 0
    _ws_header_kwarg = "additional_headers" if _ws_major >= 14 else "extra_headers"
    ws_connect_extra: dict = {_ws_header_kwarg: auth_headers}

    # Reconnect loop with exponential backoff (capped at 60 s). A production
    # backend restart or a brief network blip should NOT require the user to
    # re-run the command. Only a truly rejected handshake (401 invalid token)
    # breaks us out — at that point the operator needs a new token from the
    # web UI anyway.
    attempts = 0
    while True:
        try:
            async with websockets.connect(
                uri, max_size=4 * 1024 * 1024,
                open_timeout=15,
                close_timeout=5,
                ping_interval=20, ping_timeout=20,
                **ws_connect_extra,
            ) as ws:
                # Successful connect — reset backoff counter.
                attempts = 0
                await ws.send(json.dumps({
                    "type": "hello",
                    "version": RELAY_VERSION,
                }))
                print(f"[relay] Connected to {uri}")
                print(f"[relay] Claude binary: {ctx.claude_binary}")
                print(f"[relay] Waiting for chat messages…")

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        log.warning("Non-JSON from server: %r", raw[:200])
                        continue
                    mtype = msg.get("type")
                    if mtype == "chat":
                        mid = msg.get("message_id")
                        body = msg.get("message", "")
                        # Handle each chat concurrently so one slow Claude
                        # turn doesn't block the next incoming message.
                        asyncio.create_task(
                            _handle_and_reply(ws, ctx, mid, body)
                        )
                    elif mtype == "mpac_envelope":
                        env = msg.get("envelope") or {}
                        env_type = env.get("message_type")
                        # PROJECT_EVENT (kind=reset_to_seed) means the web
                        # backend wiped the project's files back to seed.
                        # Our resumed Claude conversation now believes in
                        # files that no longer exist. Schedule a session
                        # reset so the next chat turn starts fresh; do it
                        # in a task so the receive loop keeps running, and
                        # let the chat_lock serialize against any in-flight
                        # turn (otherwise its session_id write at completion
                        # would re-pollute our cleared state).
                        if env_type == "PROJECT_EVENT":
                            payload = env.get("payload") or {}
                            if payload.get("kind") == "reset_to_seed":
                                asyncio.create_task(_drop_session_for_reset())
                        log.debug("Received mpac_envelope: %s", env_type)
                    else:
                        log.debug("Server sent unknown type=%r", mtype)
        except websockets.exceptions.InvalidStatusCode as e:
            # 401 from the server usually means the agent token was revoked
            # (e.g. user clicked "Connect Claude" again and rotated tokens).
            # Bail — reconnecting forever with a dead token is wasteful.
            status = getattr(e, 'status_code', None)
            if status in (401, 403):
                print(
                    f"error: WebSocket handshake rejected ({e}). "
                    f"Token is invalid or revoked. Click 'Connect Claude' "
                    f"in the web app to get a fresh command.",
                    file=sys.stderr,
                )
                return 3
            # Other status codes: backoff and retry (maybe backend booting).
            log.warning("WS handshake unexpected status: %s", e)
        except (websockets.exceptions.ConnectionClosed,
                ConnectionRefusedError, OSError) as e:
            log.info("Disconnected: %s", e)

        attempts += 1
        delay = min(2 ** min(attempts, 6), 60)  # 2, 4, 8, 16, 32, 64→60 cap
        print(f"[relay] Reconnecting in {delay}s… (attempt {attempts})")
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return 0


async def _handle_and_reply(ws, ctx: RelayContext, message_id: str, body: str) -> None:
    reply = await handle_chat(ctx, body)
    try:
        await ws.send(json.dumps({
            "type": "chat_reply",
            "message_id": message_id,
            "reply": reply,
        }))
    except Exception:
        log.exception("Failed to send chat_reply (ws closed?)")


# ── Entry point ─────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Optional event recorder — see web-app/api/main.py for the same hook.
    # No-op when the package is missing or MPAC_EVENT_LOG is unset.
    #
    # Layout-aware search: in a dev checkout this file lives at
    # mpac-mcp/src/mpac_mcp/relay.py (repo root is up 4 levels). When pip-
    # installed (typical relay user), `mpac_event_recorder/` is NOT on the
    # site-packages path — the user has to set PYTHONPATH=<repo> manually
    # if they want relay-side recording. The walk below finds the dev
    # case automatically and silently skips the pip case.
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        for _depth in range(1, 6):
            _candidate = os.path.abspath(
                os.path.join(_here, *([".."] * _depth))
            )
            if os.path.isdir(os.path.join(_candidate, "mpac_event_recorder")):
                if _candidate not in sys.path:
                    sys.path.insert(0, _candidate)
                break
        import mpac_event_recorder  # type: ignore[import-not-found]
        mpac_event_recorder.install_relay()
    except ImportError:
        pass
    except Exception:
        log.exception("mpac_event_recorder bootstrap failed; continuing without it")
    try:
        return asyncio.run(run_relay(args))
    except KeyboardInterrupt:
        print("\n[relay] Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
