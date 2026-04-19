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
    "  - withdraw_intent(intent_id, reason)\n\n"
    "When the user asks about ANY file (e.g. `src/api.py`, `README.md`), "
    "assume they mean a file inside the shared project. Do NOT say it "
    "doesn't exist until you've checked with list_project_files() or "
    "read_project_file().\n\n"
    "Protocol when editing files:\n"
    "  1. If uncertain what's in the project, call list_project_files first.\n"
    "  2. BEFORE editing, call check_overlap(files) to see if anyone else "
    "is working on them. If overlap exists, tell the user and ask to proceed "
    "or yield.\n"
    "  3. Call announce_intent(files, objective) BEFORE the first write. "
    "Remember the returned intent_id.\n"
    "  4. For each file: read_project_file → decide change → write_project_file "
    "with the FULL new content (these tools don't support diffs).\n"
    "  5. When done, ALWAYS call withdraw_intent(intent_id) — even on "
    "abandonment or failure. Don't leave dangling intents.\n\n"
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


async def handle_chat(ctx: RelayContext, message: str) -> str:
    """Spawn `claude -p` with MCP_CONNECTION_BLOCKING=1 + the mpac-coding
    MCP server and return its stdout.

    Errors are caught and returned as a user-facing message so the web app
    chat always gets SOMETHING back — surfacing relay failures in-line is
    more useful than a spinning loader.
    """
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
        log.info("Spawning claude -p (msg len=%d, mcp_config=%s)",
                 len(message), mcp_config_path)
        try:
            proc = await asyncio.create_subprocess_exec(
                ctx.claude_binary, "-p",
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
                message,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=CLAUDE_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
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
            log.warning("claude -p exit=%s stderr=%r",
                        proc.returncode, err[:500])
            if "login" in err.lower() or "auth" in err.lower():
                return (
                    f"[relay] Claude Code isn't authenticated on this machine.\n"
                    f"Run `claude /login` in a terminal, then retry.\n\n"
                    f"Raw error: {err[:400]}"
                )
            return (f"[relay] Claude Code failed "
                    f"(exit {proc.returncode}): {err[:400]}")

        reply = stdout.decode("utf-8", errors="replace").rstrip()
        log.info("claude -p completed reply_len=%d", len(reply))
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
    sep = "&" if "?" in uri else "?"
    full_uri = f"{uri}{sep}token={args.token}"
    log.info("Connecting to %s", uri)

    # Reconnect loop with exponential backoff (capped at 60 s). A production
    # backend restart or a brief network blip should NOT require the user to
    # re-run the command. Only a truly rejected handshake (401 invalid token)
    # breaks us out — at that point the operator needs a new token from the
    # web UI anyway.
    attempts = 0
    while True:
        try:
            async with websockets.connect(
                full_uri, max_size=4 * 1024 * 1024,
                open_timeout=15,
                close_timeout=5,
                ping_interval=20, ping_timeout=20,
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
                        # MVP: we don't react to coordinator envelopes yet.
                        log.debug("Received mpac_envelope: %s",
                                  msg.get("envelope", {}).get("message_type"))
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
    try:
        return asyncio.run(run_relay(args))
    except KeyboardInterrupt:
        print("\n[relay] Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
