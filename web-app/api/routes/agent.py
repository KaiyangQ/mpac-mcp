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
from ..mpac_bridge import process_envelope, registry as session_registry
from ..schemas import (
    AgentAnnounceIntent,
    AgentAnnounceIntentResponse,
    AgentOverlapQuery,
    AgentOverlapResponse,
    AgentStatusResponse,
    AgentTokenResponse,
    AgentWithdrawIntent,
)
from mpac_protocol.core.models import Scope

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


@router.post("/projects/{project_id}/agent-token", response_model=AgentTokenResponse)
def mint_agent_token(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint (or rotate) the caller's agent token for this project.

    Idempotent per user/project pair in the sense that we revoke the prior
    unrevoked agent Token before issuing a new one — the user only ever has
    one live relay credential at a time. Calling the endpoint twice is safe
    and simply rotates the token (old relay disconnects on next use).
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

    # Revoke any prior agent tokens for this user/project so the "latest copy
    # wins" — avoids dangling zombie relays when the user runs the modal twice.
    prior = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_agent == True,  # noqa: E712
        Token.is_revoked == False,  # noqa: E712
    ).all()
    for t in prior:
        t.is_revoked = True

    token = Token(
        token_value=secrets.token_urlsafe(32),
        user_id=user.id,
        project_id=project_id,
        roles=json.dumps(["agent"]),
        is_agent=True,
    )
    db.add(token)
    db.commit()
    db.refresh(token)

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
    envelope = conn.participant.announce_intent(
        session_id=session.mpac_session_id,
        intent_id=intent_id,
        objective=req.objective,
        scope=Scope(kind="file_set", resources=list(req.files)),
    )
    await process_envelope(session, envelope, conn.principal_id)
    log.info("Agent intent announced: user=%s files=%s intent_id=%s",
             user.id, req.files, intent_id)
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
        hit = proposed & their_files
        if not hit:
            continue
        other_display = session.connections.get(intent.principal_id)
        overlaps.append({
            "principal_id": intent.principal_id,
            "display_name": other_display.display_name if other_display else intent.principal_id,
            "files": sorted(hit),
            "objective": intent.objective,
        })
    return AgentOverlapResponse(overlaps=overlaps)
