"""Agent relay (Path B variant 2) — mint tokens for the local Claude Code relay.

Flow:
  1. User visits project page, clicks "Connect Claude" → POST /api/projects/{id}/agent-token
  2. Backend mints a Token row with is_agent=True, returns bearer + a ready-to-run
     shell command pasted into the modal.
  3. User runs the command locally; mpac-mcp-relay connects to /ws/relay/{project_id}
     with the bearer token in a ?token= query param.
  4. Backend registers the agent as an MPAC participant in that project's session
     (see routes/ws_relay.py).

The token is a plain Token row (is_agent=True), so the existing membership logic
(_assert_member etc.) treats it as a valid project credential — BUT the /ws/relay
and /ws/session endpoints cross-check is_agent to route it to the right place.

Milestone B additionally exposes /api/agent/intents — HTTP endpoints the relay's
`claude -p` MCP subprocess uses to announce / withdraw intents on the agent's
behalf. Those push real MPAC envelopes through the coordinator so the user's
browser sees the agent's intent appear in WHO'S WORKING in real time.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_user_or_agent
from ..config import IS_PRODUCTION
from ..database import get_db
from ..models import Project, Token, User
from ..mpac_bridge import build_file_scope, compute_scope_impact, process_envelope, registry as session_registry
from ..schemas import (
    AgentActiveIntentsResponse,
    AgentAnnounceIntent,
    AgentAnnounceIntentResponse,
    AgentOverlapQuery,
    AgentOverlapResponse,
    AgentStatusResponse,
    AgentTokenResponse,
    AgentWithdrawIntent,
)
from mpac_protocol.core.models import IntentState, Scope

log = logging.getLogger("mpac.agent")

router = APIRouter()


def _public_ws_base() -> str:
    """Where should the relay dial? Dev = localhost:8001; prod = env-override.

    Shown to the user in the copy-paste command; must be reachable from their
    laptop. In dev we default to ws://127.0.0.1:8001 (single-machine testing).
    In prod set MPAC_WEB_PUBLIC_WS to wss://<host> so the command works for
    users on other machines.
    """
    override = os.environ.get("MPAC_WEB_PUBLIC_WS")
    if override:
        return override
    return "wss://mpac-web.duckdns.org" if IS_PRODUCTION else "ws://127.0.0.1:8001"


def _public_http_base() -> str:
    """HTTP(S) counterpart of :func:`_public_ws_base` — used to embed a
    ``curl -fsSL`` URL inside the launch_command so the bootstrap.sh
    endpoint can be fetched from the user's terminal."""
    override = os.environ.get("MPAC_WEB_PUBLIC_HTTP")
    if override:
        return override
    return "https://mpac-web.duckdns.org" if IS_PRODUCTION else "http://127.0.0.1:8001"


def _rotate_agent_token(db: Session, user_id: int, project_id: int) -> Token:
    """Revoke any live agent tokens for (user, project) and mint a fresh one.

    Used when no relay is actively connected — it's safe to rotate because
    no in-flight MCP HTTP call will be holding the old value.
    """
    prior = db.query(Token).filter(
        Token.user_id == user_id,
        Token.project_id == project_id,
        Token.is_agent == True,  # noqa: E712
        Token.is_revoked == False,  # noqa: E712
    ).all()
    for t in prior:
        t.is_revoked = True
    token = Token(
        token_value=secrets.token_urlsafe(32),
        user_id=user_id,
        project_id=project_id,
        roles=json.dumps(["agent"]),
        is_agent=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.post("/projects/{project_id}/agent-token", response_model=AgentTokenResponse)
def mint_agent_token(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint (or reuse) the caller's agent token for this project.

    UX policy: if a relay is CURRENTLY connected for this (user, project),
    we return the SAME token the running relay is already using. This keeps
    "open the modal to copy the command again" from silently killing an
    active relay (which was the original 2026-04-18 design and turned out
    to be surprising — opening the modal would revoke the token the running
    relay was using for MCP HTTP calls, and every subsequent tool call 401'd).

    If no relay is connected (or the prior token got somehow lost), we mint
    a fresh one and revoke any stale prior tokens, as before.
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Must already be a member (hold a non-revoked user Token).
    membership = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_agent == False,  # noqa: E712
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not membership:
        raise HTTPException(403, "You are not a member of this project")

    # If a relay is actively connected for this (user, project), reuse the
    # token it's currently holding. Walk the in-memory RelayRegistry.
    from .ws_relay import relay_registry  # lazy import — circular
    relay = relay_registry._by_key.get((user.id, project_id))  # noqa: SLF001
    if relay is not None:
        # Find the live token the relay used to authenticate — the only
        # not-revoked agent token for this (user, project). If for any
        # reason there's a mismatch, fall through and rotate.
        existing = db.query(Token).filter(
            Token.user_id == user.id,
            Token.project_id == project_id,
            Token.is_agent == True,  # noqa: E712
            Token.is_revoked == False,  # noqa: E712
        ).order_by(Token.id.desc()).first()
        if existing is not None:
            token = existing
            # Skip revoke-and-mint — return the live token unchanged.
            # Fall through to response-building below.
            pass  # token is set
        else:
            # Shouldn't normally happen (registry says connected but DB has
            # no live token) — rotate to recover.
            token = _rotate_agent_token(db, user.id, project_id)
    else:
        token = _rotate_agent_token(db, user.id, project_id)

    ws_base = _public_ws_base()
    http_base = _public_http_base()
    relay_url = f"{ws_base}/ws/relay/{project_id}"
    # v0.2.5 UX: the copy-paste is ONE line that fetches a server-
    # generated bootstrap script. That script handles everything a
    # first-time user needs: install Claude Code if missing, run
    # ``claude /login`` (opens browser) if not logged in, install
    # mpac-mcp, and finally exec the relay. Single paste, no
    # prerequisites beyond Node + Python.
    #
    # Why ``bash <(curl ...)`` and not ``curl | bash``: process
    # substitution keeps the script's stdin as a real TTY so the
    # interactive ``claude /login`` prompt works. With a pipe, claude
    # would lose access to the terminal.
    bootstrap_sh_url = (
        f"{http_base}/api/projects/{project_id}/bootstrap.sh"
        f"?token={token.token_value}"
    )
    bootstrap_ps1_url = (
        f"{http_base}/api/projects/{project_id}/bootstrap.ps1"
        f"?token={token.token_value}"
    )
    # ``bash <(…)`` (process substitution) keeps stdin as a real TTY so
    # the interactive ``claude /login`` prompt works. ``curl | bash`` would
    # consume stdin and leave claude unable to read the paste-back code.
    launch_command = f"bash <(curl -fsSL '{bootstrap_sh_url}')"
    # PowerShell equivalent: download to memory, invoke as a script block.
    # ``iex (irm …)`` is the classic form and works for our use case
    # because ``claude /login`` opens an OS browser — it doesn't need
    # stdin in the PS pipeline.
    launch_command_windows = f"iex (irm '{bootstrap_ps1_url}')"

    return AgentTokenResponse(
        token_value=token.token_value,
        project_id=project_id,
        relay_url=relay_url,
        launch_command=launch_command,
        launch_command_windows=launch_command_windows,
    )


@router.get("/projects/{project_id}/agent-status", response_model=AgentStatusResponse)
def agent_status(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Is this user's relay currently connected to this project?

    The source of truth is the in-memory relay registry (see routes/ws_relay.py).
    We import lazily to avoid circular imports at module load.
    """
    # Membership check
    membership = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not membership:
        raise HTTPException(403, "You are not a member of this project")

    from .ws_relay import relay_registry  # lazy import

    connected = relay_registry.is_connected(user.id, project_id)
    display_name = f"{user.display_name}'s Claude" if connected else None
    return AgentStatusResponse(connected=connected, display_name=display_name)


# ── Milestone B: agent intent endpoints ─────────────────────────────────
#
# These are called by the `claude -p` MCP subprocess (see mpac_mcp.relay_tools)
# on the user's laptop, NOT by the browser. Auth uses the same MPAC bearer
# token that the relay itself holds — we look up the corresponding agent
# participant via the active ProjectSession.

def _get_agent_conn(project_id: int, user_id: int):
    """Find the agent participant's _ConnectedParticipant in the session registry.

    Returns (session, conn). Raises HTTPException(409) if the agent isn't
    currently connected — relay needs to be running for intent ops to work.
    """
    # SessionRegistry stores sessions in a private dict; peek directly.
    session = session_registry._sessions.get(project_id)  # noqa: SLF001
    if session is None:
        raise HTTPException(409, "No active MPAC session — relay disconnected?")
    principal_id = f"agent:user-{user_id}"
    conn = session.connections.get(principal_id)
    if conn is None:
        raise HTTPException(
            409,
            f"Agent {principal_id} not registered in session. Is the relay running?",
        )
    return session, conn


@router.post("/agent/intents", response_model=AgentAnnounceIntentResponse)
async def agent_announce_intent(
    req: AgentAnnounceIntent,
    user: User = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Agent (via its local claude -p MCP subprocess) declares it intends to
    edit the given files. Broadcasts INTENT_ANNOUNCE through the coordinator
    so every connected browser sees the agent's active_intent + scope.
    """
    # Membership
    member = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == req.project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this project")

    session, conn = _get_agent_conn(req.project_id, user.id)
    intent_id = f"intent-agent-{user.id}-{uuid.uuid4().hex[:10]}"
    scope = build_file_scope(
        list(req.files),
        db=db, project_id=req.project_id,
        affects_symbols=req.symbols,
    )
    envelope = conn.participant.announce_intent(
        session_id=session.mpac_session_id,
        intent_id=intent_id,
        objective=req.objective,
        scope=scope,
    )
    await process_envelope(session, envelope, conn.principal_id)
    ext = scope.extensions or {}
    log.info(
        "Agent intent announced: user=%s files=%s impact=%s "
        "symbols=%s intent_id=%s",
        user.id, req.files,
        ext.get("impact"),
        ext.get("affects_symbols"),
        intent_id,
    )
    return AgentAnnounceIntentResponse(intent_id=intent_id, accepted=True)


@router.delete("/agent/intents")
async def agent_withdraw_intent(
    req: AgentWithdrawIntent,
    user: User = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Withdraw a previously-announced agent intent (when Claude is done)."""
    member = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == req.project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this project")

    session, conn = _get_agent_conn(req.project_id, user.id)
    envelope = conn.participant.withdraw_intent(
        session_id=session.mpac_session_id,
        intent_id=req.intent_id,
        reason=req.reason,
    )
    await process_envelope(session, envelope, conn.principal_id)
    log.info("Agent intent withdrawn: user=%s intent_id=%s reason=%s",
             user.id, req.intent_id, req.reason)
    return {"status": "withdrawn", "intent_id": req.intent_id}


@router.post("/agent/overlap", response_model=AgentOverlapResponse)
async def agent_check_overlap(
    req: AgentOverlapQuery,
    user: User = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Check which OTHER active participants have intents overlapping with
    the proposed file set. Returns empty list when there are no overlaps.

    The agent's MCP tool `check_overlap` calls this BEFORE announce_intent so
    Claude can decide to yield or escalate if a human is already editing the
    same file.
    """
    member = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == req.project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this project")

    session, conn = _get_agent_conn(req.project_id, user.id)
    proposed = set(req.files)
    # v0.2.1: compute our prospective impact set up-front so we can also
    # spot dependency_breakage against intents already in flight. An 0.2.0
    # coordinator/peer that never populates ``extensions.impact`` just
    # never contributes to the dep-conflict side of this reducer, which
    # matches the fallback-to-path-overlap semantics we promised.
    my_impact = set(compute_scope_impact(db, req.project_id, list(req.files)))
    overlaps: list[dict] = []
    # Coordinator.intents is the source of truth for live intents (the conn
    # objects don't carry intent state — frontends derive it from broadcasts).
    for intent_id, intent in session.coordinator.intents.items():
        if intent.principal_id == conn.principal_id:
            continue
        # Only consider intents that are still active (not terminated).
        if intent.state_machine.state in ("Withdrawn", "Completed", "Terminated"):
            continue
        scope = intent.scope
        their_files = set(scope.resources) if scope else set()
        their_impact: set[str] = set()
        if scope and scope.extensions:
            raw = scope.extensions.get("impact")
            if isinstance(raw, list):
                their_impact = {x for x in raw if isinstance(x, str)}

        direct_hit = proposed & their_files
        # Cross-file: we'd edit a file they've claimed via reverse-dep,
        # OR they'd edit a file we've claimed via reverse-dep.
        dep_hit = (my_impact & their_files) | (their_impact & proposed)
        if not direct_hit and not dep_hit:
            continue

        other_display = session.connections.get(intent.principal_id)
        overlaps.append({
            "principal_id": intent.principal_id,
            "display_name": other_display.display_name if other_display else intent.principal_id,
            "files": sorted(direct_hit),
            "dependency_files": sorted(dep_hit),
            "objective": intent.objective,
            "category": "scope_overlap" if direct_hit else "dependency_breakage",
        })
    return AgentOverlapResponse(overlaps=overlaps)


@router.get(
    "/agent/projects/{project_id}/intents",
    response_model=AgentActiveIntentsResponse,
)
async def agent_list_active_intents(
    project_id: int,
    user: User = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """v0.2.4: return every live intent in the project EXCEPT the caller's.

    The MCP relay's ``list_active_intents()`` tool calls this so a Claude
    can learn the whole team's state before announcing its own intent —
    not just the overlap subset. Callers get back enough info
    (``objective``, ``symbols``, ``files``) to reason about whether their
    planned work will collide with anyone.

    Excluded explicitly:
      * the caller's own intents (no self-noise)
      * terminal-state intents (Withdrawn / Completed / Terminated)

    Read-only. No side effects. Safe to call as often as an agent wants.
    """
    member = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this project")

    # Deliberately NOT using _get_agent_conn — this endpoint is read-only
    # and shouldn't fail just because the caller's relay happens to be
    # down or the caller is a human looking at the dashboard. We only
    # need enough to know WHICH principal ids represent this user (so we
    # can exclude them from the returned list).
    session = session_registry.get(project_id)
    if session is None:
        return AgentActiveIntentsResponse(intents=[])

    # A single user can show up as both a human (``user:42``) and that
    # user's agent relay (``agent:user-42``). Exclude both flavours from
    # the reply so the caller doesn't get "you're working on X" noise.
    self_prefixes = {f"user:{user.id}", f"agent:user-{user.id}"}

    # Only surface intents in live states — matches what
    # coordinator._detect_scope_overlaps considers relevant. Checking the
    # ``current_state`` enum (not a string) — the coordinator's state
    # machines store ``IntentState`` members, not their .value.
    live_states = {IntentState.ACTIVE, IntentState.SUSPENDED, IntentState.ANNOUNCED}

    intents: list[dict] = []
    for intent_id, intent in session.coordinator.intents.items():
        if intent.principal_id in self_prefixes:
            continue
        if intent.state_machine.current_state not in live_states:
            continue

        scope = intent.scope
        files = list(scope.resources) if scope and scope.resources else []
        symbols: list[str] = []
        if scope and scope.extensions:
            raw = scope.extensions.get("affects_symbols")
            if isinstance(raw, list):
                symbols = [s for s in raw if isinstance(s, str)]

        # Fallback display name via the connections map — principal_id is
        # opaque (``user:42`` / ``agent:user-42``) and not friendly.
        other = session.connections.get(intent.principal_id)
        display = other.display_name if other else intent.principal_id
        is_agent = intent.principal_id.startswith("agent:")

        intents.append({
            "intent_id": intent_id,
            "principal_id": intent.principal_id,
            "display_name": display,
            "files": files,
            "symbols": symbols,
            "objective": intent.objective,
            "is_agent": is_agent,
        })

    # Sort for deterministic output so downstream prompts don't flap.
    intents.sort(key=lambda i: (i["principal_id"], i["intent_id"]))
    return AgentActiveIntentsResponse(intents=intents)


# ── Bootstrap script endpoint (served raw, no OpenAPI schema) ──────────

# Minimum mpac-mcp version the bootstrap script will install. Bump when a
# new tool or required field lands so fresh users get it. Kept as a module
# constant so the agent-token response and the rendered script agree.
_MIN_MPAC_MCP = "0.2.2"


def _render_bootstrap_sh(relay_url: str, token_value: str) -> str:
    """Render the one-shot install-and-connect shell script.

    The script auto-installs Claude Code (if missing), runs ``claude
    /login`` (opens browser) if this machine hasn't authenticated yet,
    installs ``mpac-mcp`` (with fallbacks for PEP 668 / macOS system
    Python), and finally execs ``mpac-mcp-relay`` with the baked-in
    token.

    Token is interpolated into the script; don't log it, don't cache
    the rendered script anywhere.
    """
    # Raw string (``r''' '''``) so bash ``\033`` escape sequences and
    # other literal backslashes survive verbatim. Interpolation happens
    # via Python .format() on placeholders {relay_url}/{token}/{ver}
    # below — double any braces meant for bash itself.
    template = r'''#!/usr/bin/env bash
# MPAC — Connect your Claude Code to this project
#
# Auto-generated by the Connect Claude modal. Token is single-use; if
# this fails or expires grab a fresh command from the project page.
set -e

PROJECT_URL="{relay_url}"
TOKEN="{token}"
MIN_MPAC_MCP="{ver}"

say() {{ printf "\033[36m[mpac]\033[0m %s\n" "$*"; }}
die() {{ printf "\033[31m[mpac]\033[0m ✗ %s\n" "$*" >&2; exit 1; }}

# --- Hard prerequisites -------------------------------------------------
command -v python3 >/dev/null 2>&1 \
    || die "python3 not found. Install Python 3.9+: https://www.python.org/"
command -v npm >/dev/null 2>&1 \
    || die "npm not found. Install Node.js LTS: https://nodejs.org/"

# --- Claude Code CLI ----------------------------------------------------
if ! command -v claude >/dev/null 2>&1; then
    say "Installing Claude Code globally (npm install -g @anthropic-ai/claude-code)..."
    npm install -g @anthropic-ai/claude-code \
        || die "npm install failed. If this was a permissions error, try:
       sudo npm install -g @anthropic-ai/claude-code
     Then re-run the connect command from the project page."
fi

# --- Claude login (auto-opens browser) ----------------------------------
# claude stores auth under ~/.claude/. If the dir is missing, login has
# never run on this machine.
if [ ! -d "$HOME/.claude" ]; then
    say "First time on this machine. Running 'claude /login' (browser will open)..."
    say "Complete the login flow, then this script continues automatically."
    claude /login \
        || die "claude /login failed or was cancelled. Re-run the connect command once logged in."
    say "Claude authenticated."
fi

# --- mpac-mcp -----------------------------------------------------------
need_install=1
if python3 -c "import importlib.metadata as m; import sys; sys.exit(0 if m.version('mpac-mcp') >= '$MIN_MPAC_MCP' else 1)" 2>/dev/null; then
    need_install=0
fi

if [ "$need_install" -eq 1 ]; then
    say "Installing mpac-mcp >= $MIN_MPAC_MCP..."
    # Order: plain → --user → --break-system-packages. Covers venv/conda
    # users (plain works), Linux system Python (plain or --user), and
    # macOS Homebrew/system Python 3.12+ (PEP 668 externally-managed).
    if python3 -m pip install -q -U "mpac-mcp>=$MIN_MPAC_MCP" 2>/dev/null; then
        :
    elif python3 -m pip install --user -q -U "mpac-mcp>=$MIN_MPAC_MCP" 2>/dev/null; then
        USER_BIN="$(python3 -m site --user-base)/bin"
        case ":$PATH:" in
            *":$USER_BIN:"*) ;;
            *) export PATH="$USER_BIN:$PATH"
               say "Added $USER_BIN to PATH for this session." ;;
        esac
    elif python3 -m pip install --break-system-packages -q -U "mpac-mcp>=$MIN_MPAC_MCP"; then
        :
    else
        die "pip install failed. Try: pipx install --force mpac-mcp"
    fi
fi

command -v mpac-mcp-relay >/dev/null 2>&1 \
    || die "mpac-mcp-relay not on PATH after install. Check pip output above."

# --- Go -----------------------------------------------------------------
say "Connecting to $PROJECT_URL"
say "Keep this window open. Press Ctrl+C to disconnect."
exec mpac-mcp-relay --project-url "$PROJECT_URL" --token "$TOKEN"
'''
    return template.format(
        relay_url=relay_url,
        token=token_value,
        ver=_MIN_MPAC_MCP,
    )


def _render_bootstrap_ps1(relay_url: str, token_value: str) -> str:
    """PowerShell equivalent of :func:`_render_bootstrap_sh` for Windows.

    Checks for ``python`` (trying both ``python`` and ``python3``) and
    ``npm``, installs Claude Code globally if missing, auto-runs
    ``claude /login`` (opens browser via the Claude CLI itself) if
    ``%USERPROFILE%\\.claude`` doesn't yet exist, installs mpac-mcp
    with the same plain / --user / --break-system-packages fallback
    chain, then exec's the relay.

    Notes on Windows quirks handled:
    - ``python`` vs ``python3``: on Windows the command is almost always
      ``python`` (not ``python3``). We pick whichever exists.
    - User-site Scripts dir: pip --user installs to
      ``%APPDATA%\\Python\\PythonXY\\Scripts`` — if we had to go that
      route we prepend it to PATH for the session so the relay binary
      resolves.
    - $LASTEXITCODE: npm/pip don't throw in PS, they just set this.
      We check it after every external command that might fail.
    """
    template = r'''# MPAC — Connect your Claude Code to this project (Windows / PowerShell)
#
# Auto-generated by the Connect Claude modal. Token is single-use; if
# this fails or expires grab a fresh command from the project page.
$ErrorActionPreference = "Stop"

$ProjectUrl = "{relay_url}"
$Token = "{token}"
$MinMpacMcp = "{ver}"

function Say($m)  {{ Write-Host "[mpac] $m" -ForegroundColor Cyan }}
function Die($m)  {{ Write-Host "[mpac] X $m" -ForegroundColor Red; exit 1 }}

# --- Hard prerequisites -------------------------------------------------
$python = $null
if (Get-Command python -ErrorAction SilentlyContinue)  {{ $python = "python"  }}
elseif (Get-Command python3 -ErrorAction SilentlyContinue) {{ $python = "python3" }}
else {{ Die "python not found. Install Python 3.9+: https://www.python.org/" }}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {{
    Die "npm not found. Install Node.js LTS: https://nodejs.org/"
}}

# --- Claude Code CLI ----------------------------------------------------
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {{
    Say "Installing Claude Code globally (npm install -g @anthropic-ai/claude-code)..."
    npm install -g @anthropic-ai/claude-code
    if ($LASTEXITCODE -ne 0) {{
        Die "npm install failed. If this was a permissions error, open PowerShell as Administrator and re-run."
    }}
}}

# --- Claude login (auto-opens browser) ----------------------------------
# Claude stores auth under %USERPROFILE%\.claude. If missing, login has
# never run on this machine.
$claudeDir = Join-Path $env:USERPROFILE ".claude"
if (-not (Test-Path $claudeDir)) {{
    Say "First time on this machine. Running 'claude /login' (browser will open)..."
    Say "Complete the login flow, then this script continues automatically."
    claude /login
    if ($LASTEXITCODE -ne 0) {{ Die "claude /login failed or was cancelled." }}
    Say "Claude authenticated."
}}

# --- mpac-mcp -----------------------------------------------------------
$needInstall = $true
try {{
    $ver = & $python -c "import importlib.metadata as m; print(m.version('mpac-mcp'))" 2>$null
    if ($ver -and ([version]$ver -ge [version]$MinMpacMcp)) {{ $needInstall = $false }}
}} catch {{ }}

if ($needInstall) {{
    Say "Installing mpac-mcp >= $MinMpacMcp..."
    & $python -m pip install -q -U "mpac-mcp>=$MinMpacMcp" 2>$null
    if ($LASTEXITCODE -ne 0) {{
        & $python -m pip install --user -q -U "mpac-mcp>=$MinMpacMcp" 2>$null
        if ($LASTEXITCODE -ne 0) {{
            & $python -m pip install --break-system-packages -q -U "mpac-mcp>=$MinMpacMcp"
            if ($LASTEXITCODE -ne 0) {{ Die "pip install failed. Try: pipx install --force mpac-mcp" }}
        }}
        # --user went somewhere in AppData\Python\...\Scripts; prepend it so mpac-mcp-relay resolves
        $userBase = & $python -m site --user-base
        $userScripts = Join-Path $userBase "Scripts"
        if ((Test-Path $userScripts) -and -not ($env:PATH -split ';' -contains $userScripts)) {{
            $env:PATH = "$userScripts;$env:PATH"
            Say "Added $userScripts to PATH for this session."
        }}
    }}
}}

if (-not (Get-Command mpac-mcp-relay -ErrorAction SilentlyContinue)) {{
    Die "mpac-mcp-relay not on PATH after install. Check pip output above."
}}

# --- Go -----------------------------------------------------------------
Say "Connecting to $ProjectUrl"
Say "Keep this window open. Press Ctrl+C to disconnect."
& mpac-mcp-relay --project-url $ProjectUrl --token $Token
'''
    return template.format(
        relay_url=relay_url,
        token=token_value,
        ver=_MIN_MPAC_MCP,
    )


@router.get(
    "/projects/{project_id}/bootstrap.ps1",
    include_in_schema=False,
    response_class=Response,
)
def bootstrap_ps1(
    project_id: int,
    token: str,
    db: Session = Depends(get_db),
):
    """Windows/PowerShell counterpart to :func:`bootstrap_sh`.

    Served as ``text/plain`` so PowerShell's ``Invoke-RestMethod`` /
    ``Invoke-WebRequest`` both treat it as raw text. Clients fetch via
    ``iex (irm 'URL')`` which downloads + parses + executes in one step.
    """
    row = db.query(Token).filter(
        Token.token_value == token,
        Token.project_id == project_id,
        Token.is_agent == True,  # noqa: E712
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not row:
        return Response(
            content=(
                "Write-Host '[mpac] Connect token is invalid or expired.' "
                "-ForegroundColor Red\n"
                "Write-Host '[mpac] Re-open the Connect Claude modal to get a "
                "fresh command.' -ForegroundColor Red\n"
                "exit 1\n"
            ),
            media_type="text/plain; charset=utf-8",
            status_code=200,
        )

    ws_base = _public_ws_base()
    relay_url = f"{ws_base}/ws/relay/{project_id}"
    script = _render_bootstrap_ps1(relay_url, token)
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
    )


@router.get(
    "/projects/{project_id}/bootstrap.sh",
    include_in_schema=False,
    response_class=Response,
)
def bootstrap_sh(
    project_id: int,
    token: str,
    db: Session = Depends(get_db),
):
    """Return a rendered ``bash`` bootstrap script for this project.

    Authentication is the ``token`` query parameter — a live agent bearer
    for this project. We deliberately DON'T require a logged-in session
    cookie or Authorization header here: the user will be running this
    from a clean terminal via ``bash <(curl ...)``, so cookies aren't
    available and adding headers would make the copy-paste longer.

    The token itself is short-lived and single-connection: once the relay
    authenticates with it, subsequent ``/agent-token`` calls will reuse
    (not rotate) that same token while the relay is live; if no relay is
    connected yet, the user can always click Connect Claude again for a
    fresh curl URL.

    Response is ``text/plain`` — matters for ``curl | bash`` not to mung
    line-endings or inject a BOM.
    """
    row = db.query(Token).filter(
        Token.token_value == token,
        Token.project_id == project_id,
        Token.is_agent == True,  # noqa: E712
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not row:
        # Return a payload that EXITS on bash execution rather than
        # letting the shell see an HTTP error page and try to run it.
        return Response(
            content=(
                "#!/usr/bin/env bash\n"
                "echo '[mpac] Connect token is invalid or expired.' >&2\n"
                "echo '[mpac] Re-open the Connect Claude modal to get a fresh command.' >&2\n"
                "exit 1\n"
            ),
            media_type="text/plain; charset=utf-8",
            status_code=200,  # bash exits cleanly, not HTTP 404
        )

    ws_base = _public_ws_base()
    relay_url = f"{ws_base}/ws/relay/{project_id}"
    script = _render_bootstrap_sh(relay_url, token)
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
    )
