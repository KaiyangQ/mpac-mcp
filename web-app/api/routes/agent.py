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

from fastapi import APIRouter, Depends, HTTPException
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
    relay_url = f"{ws_base}/ws/relay/{project_id}"
    launch_command = (
        f"mpac-mcp-relay \\\n"
        f"  --project-url {relay_url} \\\n"
        f"  --token {token.token_value}"
    )

    return AgentTokenResponse(
        token_value=token.token_value,
        project_id=project_id,
        relay_url=relay_url,
        launch_command=launch_command,
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
