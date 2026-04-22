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
    with the file list. Returns {intent_id, accepted}. REMEMBER intent_id —
    you MUST pass it to withdraw_intent when you're done.

    Call check_overlap BEFORE this if you're not sure you have the field
    to yourself.

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
