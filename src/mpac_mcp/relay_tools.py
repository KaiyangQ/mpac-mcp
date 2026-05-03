"""Stdio MCP server exposing MPAC + project-file tools to `claude -p`.

Spawned by mpac-mcp-relay whenever the user chats. Reads config from env
vars (relay sets these) and talks back to the web app via HTTP:

  MPAC_WEB_URL          http://127.0.0.1:8001 (dev) or https URL (prod)
  MPAC_AGENT_TOKEN      the relay's bearer token
  MPAC_PROJECT_ID       "1"

Tools exposed to Claude:

  list_project_files()
      List every file path in the shared project.

  read_project_file(path)
      Read a file's current content. Claude should call this before editing
      to see the latest version (another agent or the human may have edited
      it).

  write_project_file(path, content)
      Create or overwrite a file. Full content required (not a diff). Wakes
      up everyone's browser editor immediately via the web app's WS.

  announce_intent(files, objective)
      Declare to all session participants that you're about to modify the
      given files. Returns intent_id — you MUST remember it and call
      withdraw_intent when done.

  withdraw_intent(intent_id, reason)
      Release an earlier intent.

  list_my_active_intents()    [v0.2.7]
      List intents you (this principal) currently hold open. Use when
      `claude -p` lost the intent_id from a previous turn.

  withdraw_all_my_intents(reason)    [v0.2.7]
      Bulk-withdraw every intent you hold in this project. Idempotent.

  defer_intent(files, reason, observed_intent_ids, ...)    [v0.2.9]
      Record that you saw an existing intent on these files and chose
      to YIELD without announcing. Surfaces a "yield" chip in the UI
      so the user can see your decision.

  check_overlap(files)
      BEFORE announce_intent, see whether any other participant has an
      active intent on the same files. Returns a list (empty = clear to go).

Scope / safety
--------------
All writes go through the web app's file API which runs the same path-
normalization + 1 MiB cap as the browser endpoint. The agent token is
scoped to ONE project, so Claude can't accidentally touch a different
project even if it guesses the URL.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Optional
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP


log = logging.getLogger("mpac.relay_tools")

mcp = FastMCP("mpac-coding")


# ── Config (resolved lazily so `import` works outside the subprocess) ──

def _require_env(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        # FastMCP runs stdio, so print to stderr — stdout is reserved for
        # the JSON-RPC protocol.
        print(f"[relay_tools] missing required env {name}", file=sys.stderr)
        sys.exit(2)
    return val


def _web_url() -> str:
    return _require_env("MPAC_WEB_URL")


def _agent_token() -> str:
    return _require_env("MPAC_AGENT_TOKEN")


def _project_id() -> int:
    return int(_require_env("MPAC_PROJECT_ID"))


def _client() -> httpx.Client:
    """Shared HTTP client. Short timeout because the web app is local."""
    return httpx.Client(
        base_url=_web_url(),
        headers={"Authorization": f"Bearer {_agent_token()}"},
        timeout=20.0,
    )


# ── Tools: project files ────────────────────────────────────────────────

@mcp.tool()
def list_project_files() -> dict:
    """List every file in the current project (POSIX paths, sorted)."""
    pid = _project_id()
    with _client() as c:
        r = c.get(f"/api/projects/{pid}/files")
        r.raise_for_status()
        body = r.json()
    return {
        "project_id": pid,
        "files": [f["path"] for f in body.get("files", [])],
    }


@mcp.tool()
def read_project_file(path: str) -> dict:
    """Read a single file's current content. Returns {path, content, updated_at}."""
    pid = _project_id()
    with _client() as c:
        r = c.get(
            f"/api/projects/{pid}/files/content",
            params={"path": path},
        )
        if r.status_code == 404:
            return {"error": f"File not found: {path}"}
        r.raise_for_status()
        return r.json()


@mcp.tool()
def write_project_file(path: str, content: str) -> dict:
    """Create the file if it doesn't exist, or overwrite it. Returns the new
    metadata. The web app broadcasts the change so anyone viewing that file
    in their editor will see the update immediately.

    PASS THE FULL FILE CONTENT (not a diff). If you want to edit an existing
    file, first read it with read_project_file to get the current content,
    then pass the modified full content back.
    """
    pid = _project_id()
    with _client() as c:
        r = c.put(
            f"/api/projects/{pid}/files/content",
            json={"path": path, "content": content},
        )
        if r.status_code >= 400:
            return {"error": f"write failed ({r.status_code}): {r.text[:200]}"}
        return r.json()


# ── Tools: MPAC intents ─────────────────────────────────────────────────

@mcp.tool()
def check_overlap(files: list[str]) -> dict:
    """Before announcing an intent, check if any OTHER participant is
    already working on any of these files. Returns a list of overlapping
    intents — empty list means you're clear to proceed.

    If the list is non-empty, consider:
      - yielding (don't announce) and suggesting the user wait
      - or asking the user whether to escalate (both parties try anyway)
    """
    pid = _project_id()
    with _client() as c:
        r = c.post(
            "/api/agent/overlap",
            json={"project_id": pid, "files": files},
        )
        r.raise_for_status()
        return r.json()


@mcp.tool()
def announce_intent(
    files: list[str],
    objective: str = "editing",
    symbols: list[str] | None = None,
) -> dict:
    """Announce to the whole session that you're going to modify these files.
    Every browser will see your intent appear in the 'Who's working' panel
    with the file list. REMEMBER intent_id — you MUST pass it to
    withdraw_intent when you're done.

    Call check_overlap BEFORE this if you're not sure you have the field
    to yourself.

    Possible response shapes (CHECK THE SHAPE before proceeding):

    1. **Clean accept** (no conflicts at all):
       ``{"intent_id": "...", "accepted": true, "conflicts": []}``
       → Proceed to read/write.

    2. **Accepted with same-tick dependency_breakage warning(s)** (v0.2.14+):
       ``{"intent_id": "...", "accepted": true,
          "must_surface_to_user": true,
          "surface_warning_text": "⚠️ Alice's Claude is also editing
                                    related code: changing `notes_app.db.save`
                                    in notes_app/db.py, ...",
          "guidance": "Copy `surface_warning_text` verbatim as the FIRST
                       line of your reply, then write the rest...",
          "conflicts": [{...}],
          "user_action_required": "PREFIX_REPLY_WITH_WARNING_AND_NAME_OTHER_PARTY"}``
       → COPY ``surface_warning_text`` verbatim as the FIRST line of
       your reply, then write the rest of your reply normally. Treat
       this exactly like the ``guidance`` field on the rejected branch:
       it's an instruction the tool issued you, not optional advice.
       Do NOT skip the verbatim copy because you judge your change to
       be backward-compatible (kwarg with default, new method, etc.)
       — the disclosure is independent of the safety assessment.
       The user can say "wait for X / 让路" to make you defer instead.

    3. **REJECTED with race lock** (v0.2.8+):
       ``{"rejected": true, "error_code": "STALE_INTENT", "files": [...],
          "description": "...", "guidance": "..."}``
       → DO NOT retry the same announce in THIS turn. Call defer_intent(
       files=..., observed_intent_ids=[...]) using the intent_ids you saw
       from check_overlap (or call check_overlap NOW if you didn't
       earlier), then tell the user that the same file is being modified
       by another participant and you've yielded. The user can override
       by saying "proceed anyway / 硬上" — see the v0.2.13 retry rule in
       the system prompt for what to do then.

    ``symbols`` (v0.2.1+, optional): a list of fully-qualified names you
    actually plan to change, e.g. ``["utils.foo", "utils.Cache.get"]``.
    When supplied, the coordinator can skip ``dependency_breakage``
    conflicts against other agents whose files import only OTHER symbols
    from yours. Prefer declaring symbols when you know them — it's how
    you let a teammate editing a sibling file avoid an unnecessary
    conflict. Use dotted names relative to the module (file with .py
    stripped and / replaced by dot): ``utils.py::foo`` → ``utils.foo``;
    ``pkg/sub.py::Bar.method`` → ``pkg.sub.Bar.method``. Omit if you
    don't know yet or you're touching the file broadly; the server will
    fall back to file-level detection and behaviour is identical to
    v0.2.0.
    """
    pid = _project_id()
    body: dict = {"project_id": pid, "files": files, "objective": objective}
    if symbols:
        body["symbols"] = symbols
    with _client() as c:
        r = c.post("/api/agent/intents", json=body)
        # v0.2.12: don't raise on 409 — that's the new race-lock signal
        # (server returned STALE_INTENT). Translate it into a structured
        # dict so Claude can read it as a tool result instead of crashing
        # the subprocess on an HTTPStatusError.
        if r.status_code == 409:
            try:
                detail = r.json().get("detail", {})
            except Exception:
                detail = {}
            return {
                "rejected": True,
                "error_code": detail.get("error_code", "STALE_INTENT"),
                "intent_id_attempted": detail.get("intent_id_attempted"),
                "files": detail.get("files", files),
                "description": detail.get("description", ""),
                "guidance": detail.get("guidance", ""),
            }
        r.raise_for_status()
        out = r.json()
        # v0.2.14 architecture: server (web-app v0.2.14+) is the single
        # source of truth for the parallel-work disclosure. When the
        # announce produced a same-tick dependency_breakage, server
        # populates `must_surface_to_user` / `surface_warning_text` /
        # `guidance` in the response AND queues the disclosure on the
        # /api/chat reply path so it gets prepended regardless of
        # whether Claude follows the directive (4 rounds of prompt-
        # only fixes — 0.2.12 sentinel / 0.2.13 user_action_required /
        # 0.2.14 r1 prompt reframe / 0.2.14 r2 directive fields —
        # measured 0/N compliance because Claude treats the warning
        # branch as "task complete + metadata" rather than
        # "instruction to execute"). Client just passes the response
        # through. (For backward compat against pre-v0.2.14 servers
        # that return only `conflicts: [...]`, the system prompt's
        # legacy-fallback section tells Claude to construct the ⚠️
        # string from conflicts[0] itself — no client-side generation
        # needed here.)
        return out


@mcp.tool()
def list_active_intents() -> dict:
    """List every other participant's currently-live intent in this project.

    Call this **at the start of a task** — before you know what files you'll
    touch — so you can build a picture of what the team is doing. It is the
    complement to :func:`check_overlap`: ``check_overlap`` tells you "does
    my specific file set collide with anyone"; this tool tells you the
    broader "what are people working on right now" without needing files
    up-front.

    Returns::

        {"intents": [
            {
              "intent_id": "intent-user-5-...",
              "principal_id": "user:5",
              "display_name": "Alice",
              "files": ["utils.py"],
              "symbols": ["utils.foo"],      # empty list when unspecified
              "objective": "add caching",
              "is_agent": True               # True = another Claude/MPAC agent
            },
            ...
          ]}

    Excluded automatically: your OWN intents (you already know what you're
    doing), and any intent in a terminal state.

    Recommended prompt usage: call this once at task start; quote the
    result in a one-line summary to the human ("Alice is caching utils.foo,
    Bob is adding retry to main.py"); factor it into your plan (e.g. pick
    files / symbols that don't collide with anyone).
    """
    pid = _project_id()
    with _client() as c:
        r = c.get(f"/api/agent/projects/{pid}/intents")
        r.raise_for_status()
        return r.json()


@mcp.tool()
def withdraw_intent(intent_id: str, reason: str = "done") -> dict:
    """Release an intent you announced earlier. You should always call this
    when your work on the files is complete (success OR abandonment) so
    others aren't blocked thinking you're still working.
    """
    pid = _project_id()
    with _client() as c:
        r = c.request(
            "DELETE",
            "/api/agent/intents",
            json={"project_id": pid, "intent_id": intent_id, "reason": reason},
        )
        if r.status_code >= 400:
            return {"error": f"withdraw failed ({r.status_code}): {r.text[:200]}"}
        return r.json()


@mcp.tool()
def list_my_active_intents() -> dict:
    """List intents YOU (this principal) currently hold open.

    The ``claude -p`` subprocess that backs each user message is
    one-shot — there is no memory between messages. So if you announced
    an intent in a previous turn and the user now asks you to withdraw
    it, you have no in-memory record of the ``intent_id``. Call this
    tool to rediscover your own active intents.

    Returns the same record shape as :func:`list_active_intents` (which
    excludes you). Combine the two if you want a complete picture.

    Typical usage: when a user says "withdraw" / "release" / "cancel"
    your intent and you don't have an ``intent_id`` to hand, call this
    first — pick the matching intent(s) by ``files`` / ``objective``,
    pass each ``intent_id`` to :func:`withdraw_intent`, OR just call
    :func:`withdraw_all_my_intents` to drop everything.
    """
    pid = _project_id()
    with _client() as c:
        r = c.get(f"/api/agent/projects/{pid}/intents/mine")
        r.raise_for_status()
        return r.json()


@mcp.tool()
def defer_intent(
    files: list[str],
    reason: str = "yielded",
    observed_intent_ids: list[str] | None = None,
    observed_principals: list[str] | None = None,
    ttl_sec: float = 60.0,
) -> dict:
    """v0.2.9 (mpac-mcp): record that you SAW existing intent(s) on
    ``files`` (e.g. via :func:`check_overlap`) and chose to **yield**
    without announcing one of your own.

    Use this **instead of** announce_intent when:
      * The user asked for work that overlaps with someone else's
        active intent, AND
      * You decide to back off rather than join the conflict.

    Calling this:
      * Does NOT claim any scope or lock any files.
      * Does NOT count as an Intent — it won't appear in the WHO'S
        WORKING list, and it won't trigger conflict detection against
        anyone else.
      * DOES surface a yield-chip in every participant's CONFLICTS
        panel so the human owner can see "Bob saw Alice editing X
        and yielded to her" — closing the prior UX gap where
        check_overlap-driven yields were invisible.

    Auto-clears when the observed intent(s) terminate, or after
    ``ttl_sec`` seconds (default 60), whichever comes first.

    ``observed_intent_ids`` and ``observed_principals`` come from
    :func:`check_overlap`'s return value or :func:`list_active_intents`.
    Pass them so siblings know which intent you're yielding to.
    """
    pid = _project_id()
    body: dict = {
        "project_id": pid,
        "files": files,
        "reason": reason,
        "ttl_sec": ttl_sec,
    }
    if observed_intent_ids:
        body["observed_intent_ids"] = list(observed_intent_ids)
    if observed_principals:
        body["observed_principals"] = list(observed_principals)
    with _client() as c:
        r = c.post("/api/agent/intents/defer", json=body)
        if r.status_code >= 400:
            return {"error": f"defer failed ({r.status_code}): {r.text[:200]}"}
        data = r.json()
        if (
            data.get("status") == "resolved"
            and data.get("reason") == "observed_intents_terminated"
        ):
            data["must_retry_announce"] = True
            if not data.get("guidance"):
                data["guidance"] = (
                    "The intent you yielded to is already gone. Do not tell "
                    "the user you are waiting; immediately retry by calling "
                    "check_overlap/announce_intent for the same files, then "
                    "continue or handle the new response."
                )
        return data


@mcp.tool()
def withdraw_all_my_intents(reason: str = "user_requested") -> dict:
    """Withdraw EVERY intent you currently hold in this project, in one
    call. Server-side this is bulk-withdraw, not a UI-level "yield" —
    each intent transitions to WITHDRAWN with the given reason.

    Use when:
      * The user says "withdraw" / "release" / "cancel" / "stop" and you
        don't have a specific ``intent_id`` (most common in fresh
        ``claude -p`` subprocesses where you don't remember earlier
        announces).
      * You're cleaning up after an aborted task and want to be safe.

    Idempotent. Returns ``{withdrawn_intent_ids: [...]}``; the list is
    empty if you didn't have anything to withdraw.
    """
    pid = _project_id()
    with _client() as c:
        r = c.post(
            "/api/agent/intents/withdraw_all",
            json={"project_id": pid, "reason": reason},
        )
        if r.status_code >= 400:
            return {"error": f"withdraw_all failed ({r.status_code}): {r.text[:200]}"}
        return r.json()


# ── Entry point ─────────────────────────────────────────────────────────

def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Validate env up-front so misconfig errors surface before the subprocess
    # starts its JSON-RPC loop.
    log.info(
        "Starting mpac-mcp relay_tools (project=%s web=%s)",
        _project_id(), _web_url(),
    )
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
