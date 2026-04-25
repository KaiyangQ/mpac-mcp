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

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from ..auth import AuthCtx, assert_token_scope, get_current_user, get_user_or_agent
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
    #
    # 2026-04-25 v2 — token now travels in an ``Authorization: Bearer``
    # header instead of ``?token=`` query param. Same blast-radius
    # benefit as the WS cookie switch: the URL no longer carries a
    # credential, so any intermediary proxy or diagnostic log (``curl
    # -v``, browser history if anyone opens the URL directly, etc.)
    # stops capturing it. The bootstrap route still accepts ?token= for
    # back-compat with already-pasted commands; new modal output uses
    # the header form.
    bootstrap_sh_url = (
        f"{http_base}/api/projects/{project_id}/bootstrap.sh"
    )
    bootstrap_ps1_url = (
        f"{http_base}/api/projects/{project_id}/bootstrap.ps1"
    )
    # ``bash <(…)`` (process substitution) keeps stdin as a real TTY so
    # the interactive ``claude /login`` prompt works. ``curl | bash`` would
    # consume stdin and leave claude unable to read the paste-back code.
    launch_command = (
        f'bash <(curl -fsSL -H "Authorization: Bearer {token.token_value}" '
        f"'{bootstrap_sh_url}')"
    )
    # PowerShell equivalent: download to memory, invoke as a script block.
    # ``iex (irm …)`` is the classic form and works for our use case
    # because ``claude /login`` opens an OS browser — it doesn't need
    # stdin in the PS pipeline. ``-Headers`` sets Authorization without
    # putting the token in the URL.
    launch_command_windows = (
        f"iex (irm '{bootstrap_ps1_url}' "
        f"-Headers @{{Authorization='Bearer {token.token_value}'}})"
    )

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
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Agent (via its local claude -p MCP subprocess) declares it intends to
    edit the given files. Broadcasts INTENT_ANNOUNCE through the coordinator
    so every connected browser sees the agent's active_intent + scope.
    """
    assert_token_scope(ctx, req.project_id)
    user = ctx.user
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
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Withdraw a previously-announced agent intent (when Claude is done)."""
    assert_token_scope(ctx, req.project_id)
    user = ctx.user
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
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Check which OTHER active participants have intents overlapping with
    the proposed file set. Returns empty list when there are no overlaps.

    The agent's MCP tool `check_overlap` calls this BEFORE announce_intent so
    Claude can decide to yield or escalate if a human is already editing the
    same file.
    """
    assert_token_scope(ctx, req.project_id)
    user = ctx.user
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
    # Same live-state filter as agent_list_active_intents below — using
    # ``current_state`` against the IntentState enum, NOT a hypothetical
    # ``state`` string attribute (the latter is None on every intent and
    # would let any non-running scenario throw at the line below). The
    # bug here was an AttributeError waiting to fire as soon as a peer
    # had any in-flight intent: ``check_overlap`` is the very tool agents
    # call BEFORE announcing, so the failure mode was "Claude can't even
    # ask whether it's safe to start work." Using the enum + the
    # is_terminal helper matches what coordinator.py:351 / :615 / :711
    # all do internally.
    live_states = {
        IntentState.ANNOUNCED, IntentState.ACTIVE, IntentState.SUSPENDED,
    }
    for intent_id, intent in session.coordinator.intents.items():
        if intent.principal_id == conn.principal_id:
            continue
        if intent.state_machine.current_state not in live_states:
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
    ctx: AuthCtx = Depends(get_user_or_agent),
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
    assert_token_scope(ctx, project_id)
    user = ctx.user
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
#
# 0.2.5: relay switched ``/ws/relay`` auth from ``?token=`` query to an
# Authorization header. Server side accepts both for back-compat, but
# bumping the floor here is what actually flushes ``?token=`` out of
# fresh installs — without this bump, bootstrap accepts an existing
# 0.2.4 wheel and the URL leak persists for new users too.
_MIN_MPAC_MCP = "0.2.5"


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
# mpac-mcp's transitive dep ``mcp`` requires Python >= 3.10, so the macOS
# Command Line Tools bundle (which ships python3 == 3.9.6) is NOT enough.
# Scan for explicitly versioned python3.10+ first (how Homebrew + most
# Linux package managers name them), then fall back to plain ``python3``
# if it happens to be new enough. If nothing qualifies, give the user a
# concrete install hint instead of drowning them in pip error output.
PYTHON=""
for cand in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cand" >/dev/null 2>&1; then
        PYTHON="$cand"
        break
    fi
done
if [ -z "$PYTHON" ] && command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        PYTHON="python3"
    fi
fi
if [ -z "$PYTHON" ]; then
    die "No Python >= 3.10 found. mpac-mcp requires it.
       macOS:    brew install python@3.12
       Ubuntu:   sudo apt install python3.12
       Fedora:   sudo dnf install python3.12
       Or:       https://www.python.org/downloads/"
fi
say "Using $($PYTHON --version 2>&1) at $(command -v $PYTHON)"

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
# Some Python installs (macOS CLT on older systems, some Linux distros)
# ship pip < 23 which doesn't know ``--break-system-packages``. Upgrade
# pip first if it's that old. Failures here are non-fatal; we'll notice
# again during the real install attempt and surface a useful message.
PIP_MAJOR=$($PYTHON -c "import pip; print(pip.__version__.split('.')[0])" 2>/dev/null || echo 0)
if [ "$PIP_MAJOR" -lt 23 ] 2>/dev/null; then
    say "Upgrading pip (current < 23 doesn't know --break-system-packages)..."
    $PYTHON -m pip install -q -U pip 2>/dev/null \
        || $PYTHON -m pip install -q -U --user pip 2>/dev/null \
        || true
fi

need_install=1
if $PYTHON -c "import importlib.metadata as m; import sys; sys.exit(0 if m.version('mpac-mcp') >= '$MIN_MPAC_MCP' else 1)" 2>/dev/null; then
    need_install=0
fi

if [ "$need_install" -eq 1 ]; then
    say "Installing mpac-mcp >= $MIN_MPAC_MCP (via $PYTHON)..."
    # Order: plain → --user → --break-system-packages. Covers venv/conda
    # users (plain works), Linux system Python (plain or --user), and
    # macOS Homebrew/system Python 3.12+ (PEP 668 externally-managed).
    if $PYTHON -m pip install -q -U "mpac-mcp>=$MIN_MPAC_MCP" 2>/dev/null; then
        :
    elif $PYTHON -m pip install --user -q -U "mpac-mcp>=$MIN_MPAC_MCP" 2>/dev/null; then
        USER_BIN="$($PYTHON -m site --user-base)/bin"
        case ":$PATH:" in
            *":$USER_BIN:"*) ;;
            *) export PATH="$USER_BIN:$PATH"
               say "Added $USER_BIN to PATH for this session." ;;
        esac
    elif $PYTHON -m pip install --break-system-packages -q -U "mpac-mcp>=$MIN_MPAC_MCP"; then
        :
    else
        die "pip install failed. Try: pipx install --force mpac-mcp"
    fi
fi

# After install, the relay binary might be in the Python interpreter's
# bin/ even if it's a Homebrew Python not on PATH. Add both the
# interpreter's bin and the user-site bin to PATH so we find it.
PY_BIN="$(dirname "$(command -v $PYTHON)")"
case ":$PATH:" in *":$PY_BIN:"*) ;; *) export PATH="$PY_BIN:$PATH" ;; esac

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
    ``claude /login`` (opens browser via the Claude CLI itself) if the
    CLI hasn't authenticated yet (heuristic: empty / missing
    ``%USERPROFILE%\\.claude\\sessions``), installs mpac-mcp with the
    same plain / --user / --break-system-packages fallback chain, then
    exec's the relay.

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
#
# NOTE: We intentionally use "Continue" (not "Stop"). Many native commands
# we rely on (notably pip installing pywin32) write benign WARNINGs to
# stderr; with "Stop" PowerShell wraps those as NativeCommandError and
# kills the script even when exit code = 0. We rely on $LASTEXITCODE
# checks below to decide success/failure.
$ErrorActionPreference = "Continue"

# --- Execution Policy ---------------------------------------------------
# Windows client SKUs default to ExecutionPolicy=Restricted, which blocks
# .ps1 scripts. That matters because both `npm` and `claude` on Windows
# are .ps1 shims, not .exes. Worse, the block surfaces as a
# PSSecurityException that does NOT set $LASTEXITCODE — so naive "if
# ($LASTEXITCODE -ne 0)" checks downstream miss a total failure and
# let the script "succeed" with nothing installed. Override to Bypass
# at Process scope; evaporates on shell exit, no lingering policy change.
try {{
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction Stop
}} catch {{
    $curr = Get-ExecutionPolicy
    if ($curr -in 'Restricted','AllSigned','Undefined') {{
        Write-Host "[mpac] X Group Policy pins ExecutionPolicy=$curr; Process-scope override denied." -ForegroundColor Red
        Write-Host "[mpac]   Run once (no admin needed), then re-try the iex command:" -ForegroundColor Red
        Write-Host "[mpac]     Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force" -ForegroundColor Red
        exit 1
    }}
}}

$ProjectUrl = "{relay_url}"
$Token = "{token}"
$MinMpacMcp = "{ver}"

function Say($m)  {{ Write-Host "[mpac] $m" -ForegroundColor Cyan }}
function Die($m)  {{ Write-Host "[mpac] X $m" -ForegroundColor Red; exit 1 }}

# --- Hard prerequisites -------------------------------------------------
# mpac-mcp needs Python >= 3.10 (transitive dep on ``mcp``). Prefer an
# explicitly versioned binary, then fall back to ``python`` / ``python3``
# if they're new enough. On Windows the Python installer typically only
# lays down ``python.exe`` (no python3.12.exe), so the fallback is the
# common path; explicit versions are mostly macOS-via-Bash-on-Windows
# or WSL setups.
$python = $null
foreach ($cand in @("python3.13","python3.12","python3.11","python3.10")) {{
    if (Get-Command $cand -ErrorAction SilentlyContinue) {{ $python = $cand; break }}
}}
if (-not $python) {{
    foreach ($cmd in @("python","python3")) {{
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {{
            & $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {{ $python = $cmd; break }}
        }}
    }}
}}
if (-not $python) {{
    Die "No Python >= 3.10 found. mpac-mcp requires it.
     Windows:  winget install Python.Python.3.12
     Or:       https://www.python.org/downloads/"
}}
Say "Using $(& $python --version) ($python)"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {{
    Die "npm not found. Install Node.js LTS: https://nodejs.org/"
}}

# --- Claude Code CLI ----------------------------------------------------
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {{
    Say "Installing Claude Code globally (npm install -g @anthropic-ai/claude-code)..."
    # npm.ps1 and npm.cmd can both fail in ways $LASTEXITCODE doesn't
    # capture (PSSecurityException, CommandNotFoundException) — wrap
    # in try/catch and AND $? into success detection so a silent
    # throw can't look like success.
    $npmOk = $false
    try {{
        npm install -g @anthropic-ai/claude-code
        $npmOk = ($? -and ($LASTEXITCODE -eq 0))
    }} catch {{
        Die "npm install failed to invoke: $($_.Exception.Message)"
    }}
    if (-not $npmOk) {{
        Die "npm install failed (exit=$LASTEXITCODE). If this was a permissions error, open PowerShell as Administrator and re-run."
    }}
    # npm drops claude.cmd/claude.ps1 in %APPDATA%\npm. The Node.js
    # installer adds that dir to the User-scope Path registry value,
    # but that update only reaches a *new* shell. Rebuild $env:PATH
    # from the registry in-process so claude becomes findable right now.
    $env:PATH = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {{
        Die "npm install exited 0 but 'claude' isn't on PATH. Expected it in $env:APPDATA\npm — check that npm-global dir is on your User Path."
    }}
}}

# --- Claude login (auto-opens browser) ----------------------------------
# Claude Code's auth state lives under %USERPROFILE%\.claude — but the
# directory itself is created by the CLI for unrelated reasons (project
# tracking, sessions). Existence of the dir doesn't mean we're logged in.
# Conservative heuristic: we consider ourselves logged in only if both
#   (a) the `claude` binary is on PATH (npm install above should have
#       laid it down, but be defensive), and
#   (b) there's at least one entry under .claude\sessions, which the CLI
#       only writes after a successful auth handshake.
# False negatives (forcing an extra /login) are cheap; false positives
# (skipping login when we shouldn't) leave the user staring at the relay
# silently failing later, which is much worse to debug.
$claudeDir = Join-Path $env:USERPROFILE ".claude"
$claudeInstalled = [bool](Get-Command claude -ErrorAction SilentlyContinue)
$sessions = Get-ChildItem -Path (Join-Path $claudeDir "sessions") -ErrorAction SilentlyContinue
$loggedIn = $claudeInstalled -and $sessions -and $sessions.Count -gt 0
if (-not $loggedIn) {{
    Say "Claude Code not yet authenticated on this machine. Running 'claude /login' (browser will open)..."
    Say "Complete the login flow, then this script continues automatically."
    # Same pattern as npm install above: `claude` is a .ps1 shim that
    # can throw instead of setting $LASTEXITCODE. $? catches the throw,
    # $LASTEXITCODE catches a normal non-zero exit.
    $loginOk = $false
    try {{
        claude /login
        $loginOk = ($? -and ($LASTEXITCODE -eq 0))
    }} catch {{
        Die "claude /login invocation failed: $($_.Exception.Message)"
    }}
    if (-not $loginOk) {{ Die "claude /login failed or was cancelled (exit=$LASTEXITCODE)." }}
    Say "Claude authenticated."
}}

# --- mpac-mcp -----------------------------------------------------------
# Bump ancient pip first so --break-system-packages works on the fallback.
try {{
    $pipMajor = [int](& $python -c "import pip; print(pip.__version__.split('.')[0])" 2>$null)
    if ($pipMajor -lt 23) {{
        Say "Upgrading pip (current < 23 doesn't know --break-system-packages)..."
        & $python -m pip install -q -U pip
        if ($LASTEXITCODE -ne 0) {{ & $python -m pip install -q -U --user pip }}
    }}
}} catch {{ }}

$needInstall = $true
try {{
    $ver = & $python -c "import importlib.metadata as m; print(m.version('mpac-mcp'))" 2>$null
    if ($ver -and ([version]$ver -ge [version]$MinMpacMcp)) {{ $needInstall = $false }}
}} catch {{ }}

if ($needInstall) {{
    Say "Installing mpac-mcp >= $MinMpacMcp (via $python)..."
    # Install ladder, ordered by what works for the most users first:
    #   1. --user — works for every non-venv setup (Windows non-admin global
    #      Python, macOS brew Python, Linux global Python). Inside a venv pip
    #      errors with "Can not perform a '--user' install" — that triggers
    #      step 2. --no-warn-script-location suppresses the noisy "scripts
    #      are not on PATH" line since we prepend the dir ourselves below.
    #   2. plain — catches the venv case (where --user is invalid).
    #   3. --break-system-packages — catches PEP 668 distros (Ubuntu 23+
    #      system Python, Debian 12 system Python) where both above fail.
    # Putting --user first instead of plain dodges a transient PyPI/CDN
    # race right after a publish (plain install can briefly see only old
    # versions and emit a scary "No matching distribution" ERROR before
    # a fallback retry succeeds 1-2 s later).
    & $python -m pip install --user --no-warn-script-location -q -U "mpac-mcp>=$MinMpacMcp"
    if ($LASTEXITCODE -ne 0) {{
        & $python -m pip install -q -U "mpac-mcp>=$MinMpacMcp"
        if ($LASTEXITCODE -ne 0) {{
            & $python -m pip install --break-system-packages -q -U "mpac-mcp>=$MinMpacMcp"
            if ($LASTEXITCODE -ne 0) {{ Die "pip install failed. Try: pipx install --force mpac-mcp" }}
        }}
    }}
}}

# Make sure the user-site scripts dir is on PATH for the rest of this
# session. Unconditional because the install ladder above prefers --user,
# which lays scripts down in `%APPDATA%\Python\PythonXY\Scripts` — that
# dir is *not* on PATH by default on Windows. Test-Path makes this a
# no-op when an earlier ladder step (plain in venv, or --break-system-
# packages) put the scripts somewhere already on PATH.
# We use sysconfig.get_path('scripts','nt_user') for the canonical path;
# `python -m site --user-base + 'Scripts'` gives the wrong parent dir on
# Windows (`%APPDATA%\Python\Scripts` — no version suffix).
$userScripts = & $python -c "import sysconfig, sys; print(sysconfig.get_path('scripts', 'nt_user' if sys.platform == 'win32' else 'posix_user'))"
if ((Test-Path $userScripts) -and -not ($env:PATH -split ';' -contains $userScripts)) {{
    $env:PATH = "$userScripts;$env:PATH"
    Say "Added $userScripts to PATH for this session."
}}

if (-not (Get-Command mpac-mcp-relay -ErrorAction SilentlyContinue)) {{
    Die "mpac-mcp-relay not on PATH after install. Check pip output above."
}}

# --- git-bash for Claude Code ------------------------------------------
# Claude Code CLI on Windows shells out to posix `bash` (git-bash) for some
# internal operations. Without it, `claude -p <msg>` exits 1 with the
# string "Claude Code on Windows requires git-bash" written to STDOUT
# (not stderr — yes really), which the relay surfaces as a confusing
# "Claude Code failed (exit 1): " with an empty error body. The CLI only
# auto-finds bash.exe when Git's bin dir is on $env:Path, which isn't
# the default when Git is installed to a non-C: drive. Set the env var
# explicitly so the relay's child claude.cmd inherits it.
if (-not $env:CLAUDE_CODE_GIT_BASH_PATH) {{
    $bashCandidates = @(
        "$env:ProgramFiles\Git\bin\bash.exe",
        "${{env:ProgramFiles(x86)}}\Git\bin\bash.exe",
        "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe"
    )
    # Registry wins for non-standard install drives (e.g. D:\Program Files\Git).
    try {{
        $gitRoot = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\GitForWindows' -Name InstallPath -ErrorAction SilentlyContinue).InstallPath
        if ($gitRoot) {{ $bashCandidates += (Join-Path $gitRoot 'bin\bash.exe') }}
    }} catch {{ }}
    # Last resort: bash on PATH, filtered to only accept a Git-shipped one
    # (avoids picking up WSL's /usr/bin/bash, which doesn't satisfy claude).
    $onPath = (Get-Command bash.exe -ErrorAction SilentlyContinue).Source
    if ($onPath -and ($onPath -match 'Git[\\/]bin')) {{ $bashCandidates += $onPath }}

    $bashFound = $bashCandidates | Where-Object {{ $_ -and (Test-Path $_) }} | Select-Object -First 1
    if ($bashFound) {{
        $env:CLAUDE_CODE_GIT_BASH_PATH = $bashFound
        Say "git-bash: $bashFound"
    }} else {{
        Die "git-bash not found — Claude Code CLI on Windows requires it.
     Install Git for Windows: winget install --id Git.Git -e
     Or:                      https://git-scm.com/downloads/win
     Non-standard location?   Set `$env:CLAUDE_CODE_GIT_BASH_PATH manually, then re-run."
    }}
}}

# --- Smoke-test claude -p before launching the relay ------------------
# mpac-mcp 0.2.3's relay logs "exit=1 stderr=''" when claude fails because
# it only decodes stderr — but the Claude Code CLI writes some user-facing
# errors (git-bash missing, login needed, etc.) to STDOUT instead. By the
# time a chat message hits the relay it's too late to see those. Smoke-
# test here so the real error surfaces while the user is still looking at
# this terminal. The test runs with the same env the relay inherits, so
# a passing smoke implies the chat path will succeed; a failing one
# prints claude's actual stdout for the user to act on.
function Invoke-ClaudeSmoke {{
    $out = ""
    $code = 0
    try {{
        $out = ("ping" | & claude -p --dangerously-skip-permissions 2>&1 | Out-String).Trim()
        $code = $LASTEXITCODE
    }} catch {{
        $out = "INVOCATION FAILED: $($_.Exception.Message)"
        $code = -1
    }}
    return @{{ Exit = $code; Output = $out }}
}}

Say "Smoke-testing claude -p (pre-relay sanity check)..."
$smoke = Invoke-ClaudeSmoke

# The .claude/sessions heuristic above is a LOWER BOUND on "ever logged
# in on this box" — stale sessions live there long after an OAuth token
# expires. The definitive test is actually running claude -p, which is
# what we're doing here. If it reports "Not logged in", trigger the
# login flow now (while the user is still watching this terminal) and
# retry — infinitely better than having every chat message silently fail.
if ($smoke.Exit -ne 0 -and $smoke.Output -match "(?i)not logged in|run /login|please log\s*in") {{
    Say "Claude reports Not Logged In. Running claude /login now (browser will open)..."
    Say "Complete the login flow, then this script continues automatically."
    $loginOk = $false
    try {{
        claude /login
        $loginOk = ($? -and ($LASTEXITCODE -eq 0))
    }} catch {{
        Die "claude /login invocation failed: $($_.Exception.Message)"
    }}
    if (-not $loginOk) {{ Die "claude /login failed or was cancelled (exit=$LASTEXITCODE)." }}
    Say "Re-running smoke after login..."
    $smoke = Invoke-ClaudeSmoke
}}

if ($smoke.Exit -ne 0) {{
    Write-Host "[mpac] X claude -p smoke test FAILED (exit=$($smoke.Exit))." -ForegroundColor Red
    Write-Host "[mpac]   Output from claude:" -ForegroundColor Red
    ($smoke.Output -split "`n") | ForEach-Object {{ Write-Host "[mpac]     $_" -ForegroundColor Yellow }}
    Write-Host "[mpac]   Env: CLAUDE_CODE_GIT_BASH_PATH=$env:CLAUDE_CODE_GIT_BASH_PATH" -ForegroundColor Red
    Write-Host "[mpac]   The relay will fail on every chat message until this is fixed." -ForegroundColor Red
    Write-Host "[mpac]   Proceeding to launch relay anyway so you can see the live failure pattern." -ForegroundColor Red
}} else {{
    Say "Smoke OK (claude replied $($smoke.Output.Length) chars)."
}}

# --- MCP smoke (Stage 2) ------------------------------------------------
# The bare `claude -p` smoke above proves the CLI itself runs end-to-end.
# It does NOT exercise the path the relay actually uses, which adds
# `--mcp-config <path> --strict-mcp-config` so claude spawns
# `python -m mpac_mcp.relay_tools` as a stdio MCP server before sending
# the prompt. That spawn can fail independently — wrong Python on PATH,
# mpac_mcp not importable in this venv, MCP_CONNECTION_BLOCKING off and
# the server racing — and bare-CLI smoke would never see it. Run a
# second smoke with a minimal mcp-config so the install error surfaces
# here, not on the user's first chat message.
function Invoke-ClaudeMcpSmoke {{
    $cfg = New-TemporaryFile
    try {{
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if (-not $py) {{
            return @{{ Exit = -2; Output = "python not on PATH (unexpected — bootstrap installed mpac-mcp into it earlier)" }}
        }}
        # Same shape as mpac-mcp/src/mpac_mcp/relay.py:_build_mcp_config.
        # Fake env values are fine — relay_tools only hits the web-app on
        # tool invocation, not on the initial tools/list RPC that
        # --strict-mcp-config waits for.
        $mcpConfig = @{{
            mcpServers = @{{
                "mpac-coding" = @{{
                    command = $py
                    args    = @("-m", "mpac_mcp.relay_tools")
                    env     = @{{
                        MPAC_WEB_URL     = "https://smoke.invalid/"
                        MPAC_AGENT_TOKEN = "smoke-fake-token"
                        MPAC_PROJECT_ID  = "0"
                    }}
                }}
            }}
        }} | ConvertTo-Json -Depth 6 -Compress
        $mcpConfig | Set-Content -Path $cfg -Encoding UTF8

        # MCP_CONNECTION_BLOCKING=1 makes claude wait for tools/list before
        # the prompt — without it, MCP server failures vanish silently.
        $prevBlocking = $env:MCP_CONNECTION_BLOCKING
        $env:MCP_CONNECTION_BLOCKING = "1"
        try {{
            $out = ("ping" | & claude -p `
                --mcp-config $cfg.FullName `
                --strict-mcp-config `
                --dangerously-skip-permissions 2>&1 | Out-String).Trim()
            $code = $LASTEXITCODE
        }} catch {{
            $out  = "INVOCATION FAILED: $($_.Exception.Message)"
            $code = -1
        }} finally {{
            if ($null -eq $prevBlocking) {{ Remove-Item Env:MCP_CONNECTION_BLOCKING -EA SilentlyContinue }}
            else                         {{ $env:MCP_CONNECTION_BLOCKING = $prevBlocking }}
        }}
        return @{{ Exit = $code; Output = $out }}
    }} finally {{
        Remove-Item $cfg -ErrorAction SilentlyContinue
    }}
}}

# Only run MCP smoke if Stage 1 passed — otherwise the failure here would
# just be a noisier copy of the same bare-CLI error.
if ($smoke.Exit -eq 0) {{
    Say "Smoke-testing claude -p with MCP config (catches relay_tools spawn failures)..."
    $mcpSmoke = Invoke-ClaudeMcpSmoke
    if ($mcpSmoke.Exit -ne 0) {{
        Write-Host "[mpac] X MCP smoke test FAILED (exit=$($mcpSmoke.Exit))." -ForegroundColor Red
        Write-Host "[mpac]   This means claude can run, but spawning the mpac_mcp.relay_tools" -ForegroundColor Red
        Write-Host "[mpac]   MCP server (which the relay also does on every chat) failed." -ForegroundColor Red
        Write-Host "[mpac]   Output:" -ForegroundColor Red
        ($mcpSmoke.Output -split "`n") | ForEach-Object {{ Write-Host "[mpac]     $_" -ForegroundColor Yellow }}
        Write-Host "[mpac]   Common causes:" -ForegroundColor Red
        Write-Host "[mpac]     * mpac_mcp installed into a different Python than 'python' on PATH" -ForegroundColor Red
        Write-Host "[mpac]     * stale mpac-mcp wheel that doesn't have relay_tools (pre-0.2.0)" -ForegroundColor Red
        Write-Host "[mpac]   Try:  python -m mpac_mcp.relay_tools  (should print nothing then wait on stdin)" -ForegroundColor Red
        Write-Host "[mpac]   Proceeding to launch relay anyway so you can see the live failure." -ForegroundColor Red
    }} else {{
        Say "MCP smoke OK (mpac_mcp.relay_tools loaded + tools/list returned)."
    }}
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


def _resolve_bootstrap_token(
    authorization: str | None, token_query: str | None,
) -> str | None:
    """Pull the agent bearer out of either ``Authorization: Bearer …`` (the
    new header-based path, see /agent-token launch_command) or the legacy
    ``?token=`` query param. Header wins when both are present.

    Returns ``None`` if neither is supplied — the route then renders an
    error script telling the user to re-Connect.
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip() or None
    if token_query:
        return token_query
    return None


@router.get(
    "/projects/{project_id}/bootstrap.ps1",
    include_in_schema=False,
    response_class=Response,
)
def bootstrap_ps1(
    project_id: int,
    token: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Windows/PowerShell counterpart to :func:`bootstrap_sh`.

    Served as ``text/plain`` so PowerShell's ``Invoke-RestMethod`` /
    ``Invoke-WebRequest`` both treat it as raw text. Clients fetch via
    ``iex (irm 'URL' -Headers @{Authorization='Bearer …'})`` (preferred,
    header form keeps the token out of URLs / proxy logs) or the legacy
    ``iex (irm 'URL?token=…')`` for back-compat with already-pasted
    commands.
    """
    bearer = _resolve_bootstrap_token(authorization, token)
    if not bearer:
        return Response(
            content=(
                "Write-Host '[mpac] Connect token missing.' "
                "-ForegroundColor Red\n"
                "Write-Host '[mpac] Re-open the Connect Claude modal to get "
                "a fresh command.' -ForegroundColor Red\n"
                "exit 1\n"
            ),
            media_type="text/plain; charset=utf-8",
            status_code=200,
        )
    row = db.query(Token).filter(
        Token.token_value == bearer,
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
    script = _render_bootstrap_ps1(relay_url, bearer)
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
    token: str | None = None,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return a rendered ``bash`` bootstrap script for this project.

    Authentication accepts EITHER an ``Authorization: Bearer …`` header
    (the new default — generated launch_command uses ``curl -fsSL -H
    "Authorization: Bearer …"``) OR the legacy ``?token=`` query
    parameter. The header form is preferred because it keeps the agent
    bearer out of URLs, which means out of intermediary proxy logs,
    ``curl -v`` debug dumps, browser history, etc. The query form stays
    for back-compat with already-pasted commands; expect a future hard
    cut once we're confident no one is on the old path.

    The token itself is short-lived and single-connection: once the relay
    authenticates with it, subsequent ``/agent-token`` calls will reuse
    (not rotate) that same token while the relay is live; if no relay is
    connected yet, the user can always click Connect Claude again for a
    fresh curl URL.

    Response is ``text/plain`` — matters for ``curl | bash`` not to mung
    line-endings or inject a BOM.
    """
    bearer = _resolve_bootstrap_token(authorization, token)
    if not bearer:
        return Response(
            content=(
                "#!/usr/bin/env bash\n"
                "echo '[mpac] Connect token missing.' >&2\n"
                "echo '[mpac] Re-open the Connect Claude modal to get a fresh command.' >&2\n"
                "exit 1\n"
            ),
            media_type="text/plain; charset=utf-8",
            status_code=200,
        )
    row = db.query(Token).filter(
        Token.token_value == bearer,
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
    script = _render_bootstrap_sh(relay_url, bearer)
    return Response(
        content=script,
        media_type="text/plain; charset=utf-8",
    )
