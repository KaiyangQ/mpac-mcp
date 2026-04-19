"""In-process MPAC coordinator bridge for the web app.

Design (see .claude/plans/temporal-plotting-castle.md §D.2–D.4):

FastAPI embeds one ``SessionCoordinator`` per project. Browser clients
connect via a plain WebSocket carrying our JWT; the bridge authenticates, then
acts as a thin translator between a tiny "action" vocabulary the browser uses
and full MPAC envelopes the coordinator processes.

Routing rules are copied from ``mpac_protocol.server.MPACServer.handler`` so
behavior stays consistent with the reference server:

* On inbound: ``INTENT_ANNOUNCE / INTENT_WITHDRAW / CONFLICT_ACK / …`` —
  the raw envelope is re-broadcast to everyone else in the session.
* On outbound coordinator responses: routing is message-type aware
  (``SESSION_INFO`` only to sender, ``CONFLICT_REPORT`` only to the two
  principals involved, everything else broadcast).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from mpac_protocol.core.coordinator import (
    CredentialVerifier,
    SessionCoordinator,
    VerifyResult,
)
from mpac_protocol.core.models import Scope
from mpac_protocol.core.participant import Participant
from sqlalchemy.orm import Session

from .models import Project, Token

log = logging.getLogger("mpac.bridge")


# ── Types ──────────────────────────────────────────────────────────────

# A "connection" is just something that can async-send a JSON-serialisable
# dict. Browsers use WebSocket; the in-process Claude agent uses a loopback
# that simply feeds responses back into its own message handler. This
# indirection keeps the bridge agnostic of FastAPI's WebSocket type.
Connection = Callable[[Dict[str, Any]], Awaitable[None]]


# Inbound message types whose raw envelope should be re-broadcast to everyone
# else in the session (matches mpac_protocol.server.MPACServer).
_BROADCAST_INBOUND_TYPES = frozenset({
    "OP_COMMIT", "INTENT_ANNOUNCE", "INTENT_WITHDRAW", "INTENT_UPDATE",
    "CONFLICT_ACK", "CONFLICT_ESCALATE", "RESOLUTION",
})

# Outbound response types that go ONLY to the original sender.
_UNICAST_RESPONSE_TYPES = frozenset({
    "PROTOCOL_ERROR", "SESSION_INFO", "OP_REJECT", "INTENT_CLAIM_STATUS",
})


def _synth_participant_update(
    session_id: str, conn: "_ConnectedParticipant", status: str,
) -> Dict[str, Any]:
    """Build a bridge-synthesized PARTICIPANT_UPDATE envelope.

    The MPAC coordinator itself doesn't emit "X joined" notifications — it
    just accepts HELLO and returns SESSION_INFO to the joiner. But every
    browser needs to learn the display names of participants as they come
    and go, so the bridge fills this gap by broadcasting a lightweight
    ``PARTICIPANT_UPDATE`` on each connect / disconnect. The frontend's
    `useMpacSession` hook already handles this message type.
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "protocol": "MPAC",
        "version": "0.1.13",
        "message_type": "PARTICIPANT_UPDATE",
        "message_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": {
            "principal_id": f"service:bridge-{session_id}",
            "principal_type": "coordinator",
            "sender_instance_id": f"service:bridge-{session_id}",
        },
        "ts": now,
        "payload": {
            "principal_id": conn.principal_id,
            "status": status,  # "online" | "offline"
            "display_name": conn.display_name,
            "principal_type": conn.principal_type,
            "roles": conn.roles,
            "is_agent": conn.is_agent,
        },
    }


@dataclass
class _ConnectedParticipant:
    principal_id: str
    participant: Participant
    send: Connection
    display_name: str
    principal_type: str
    roles: List[str]
    is_agent: bool = False


@dataclass
class ProjectSession:
    """One per project_id. Owns the coordinator + connected participants."""

    project_id: int
    mpac_session_id: str
    coordinator: SessionCoordinator
    connections: Dict[str, _ConnectedParticipant] = field(default_factory=dict)

    def presence_snapshot(self) -> List[Dict[str, Any]]:
        """For debugging: who is currently connected."""
        return [
            {
                "principal_id": p.principal_id,
                "display_name": p.display_name,
                "principal_type": p.principal_type,
                "is_agent": p.is_agent,
                "roles": p.roles,
            }
            for p in self.connections.values()
        ]


class SessionRegistry:
    """Process-wide registry of ProjectSessions, one per project_id."""

    def __init__(self) -> None:
        self._sessions: Dict[int, ProjectSession] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        project_id: int,
        mpac_session_id: str,
        verifier: CredentialVerifier,
    ) -> ProjectSession:
        async with self._lock:
            existing = self._sessions.get(project_id)
            if existing is not None:
                return existing
            coord = SessionCoordinator(
                session_id=mpac_session_id,
                security_profile="authenticated",
                credential_verifier=verifier,
            )
            session = ProjectSession(
                project_id=project_id,
                mpac_session_id=mpac_session_id,
                coordinator=coord,
            )
            self._sessions[project_id] = session
            log.info(
                "Created MPAC session project_id=%s mpac_session_id=%s",
                project_id, mpac_session_id,
            )
            return session

    def get(self, project_id: int) -> Optional[ProjectSession]:
        return self._sessions.get(project_id)


# Singleton for this process.
registry = SessionRegistry()


class AgentTokenRegistry:
    """Per-project in-memory allowlist for ephemeral agent bearer tokens.

    The verifier closure produced by ``build_verifier_for_project`` checks this
    registry *in addition to* the DB. The agent module mints + registers a
    token just before joining a session, then removes it on teardown. This
    lets agents participate under the Authenticated profile without DB rows.
    """

    def __init__(self) -> None:
        self._tokens: Dict[int, set[str]] = {}

    def add(self, project_id: int, token: str) -> None:
        self._tokens.setdefault(project_id, set()).add(token)

    def remove(self, project_id: int, token: str) -> None:
        bucket = self._tokens.get(project_id)
        if bucket:
            bucket.discard(token)
            if not bucket:
                self._tokens.pop(project_id, None)

    def has(self, project_id: int, token: str) -> bool:
        bucket = self._tokens.get(project_id)
        return bool(bucket and token in bucket)


agent_tokens = AgentTokenRegistry()


# ── Credential verifier backed by our SQLite ───────────────────────────

def build_verifier_for_project(db: Session, project_id: int) -> CredentialVerifier:
    """Return a verifier that accepts any non-revoked Token on this project.

    The Token table covers both humans (via invite) and the Claude agent
    (Phase E mints an ``is_agent=True`` Token). Both go through the same path.
    """

    def verify(credential: Dict[str, Any], session_id: str) -> VerifyResult:
        if not isinstance(credential, dict):
            return VerifyResult.reject("credential must be an object")
        if credential.get("type") != "bearer_token":
            return VerifyResult.reject("only bearer_token credentials are supported")
        value = credential.get("value")
        if not value:
            return VerifyResult.reject("missing credential value")
        # Ephemeral agent tokens (in-memory, minted per chat turn) — accepted
        # as contributor. Check this before the DB so we don't need a row.
        if agent_tokens.has(project_id, value):
            return VerifyResult.accept(granted_roles=["contributor"])
        # Re-query the DB on every HELLO so revocation is instant.
        # (For a live session, the verifier is called once per join — cheap.)
        token_row = (
            db.query(Token)
            .filter(
                Token.project_id == project_id,
                Token.token_value == value,
                Token.is_revoked == False,  # noqa: E712
            )
            .first()
        )
        if not token_row:
            return VerifyResult.reject("bearer token not authorized for this project")
        try:
            roles = json.loads(token_row.roles)
        except (TypeError, json.JSONDecodeError):
            roles = ["contributor"]
        return VerifyResult.accept(granted_roles=roles)

    return verify


# ── Simplified browser action → MPAC envelope ──────────────────────────

def browser_action_to_envelope(
    action: Dict[str, Any], participant: Participant, session_id: str,
) -> Optional[Dict[str, Any]]:
    """Translate a tiny browser action vocabulary into an MPAC envelope.

    Returns ``None`` for unknown actions (the caller should drop them).
    """
    kind = action.get("action")

    if kind == "begin_task":
        files = action.get("files") or []
        intent_id = action.get("intent_id") or f"intent-{uuid.uuid4().hex[:12]}"
        objective = action.get("objective") or "editing"
        scope = Scope(kind="file_set", resources=list(files))
        return participant.announce_intent(
            session_id=session_id,
            intent_id=intent_id,
            objective=objective,
            scope=scope,
        )

    if kind == "yield_task":
        intent_id = action.get("intent_id")
        if not intent_id:
            return None
        return participant.withdraw_intent(
            session_id=session_id,
            intent_id=intent_id,
            reason=action.get("reason") or "user_yielded",
        )

    if kind == "ack_conflict":
        conflict_id = action.get("conflict_id")
        if not conflict_id:
            return None
        return participant.ack_conflict(
            session_id=session_id,
            conflict_id=conflict_id,
        )

    if kind == "heartbeat":
        return participant.heartbeat(
            session_id=session_id,
            status=action.get("status") or "working",
            active_intent_id=action.get("active_intent_id"),
        )

    return None


# ── Core message-processing hot loop ───────────────────────────────────

async def process_envelope(
    session: ProjectSession,
    envelope: Dict[str, Any],
    sender_principal_id: str,
) -> None:
    """Feed an envelope through the coordinator and route responses.

    Mirrors `MPACServer.handler` logic. Exceptions are logged and swallowed —
    a misbehaving client shouldn't take down the session.
    """
    msg_type = envelope.get("message_type", "?")
    try:
        responses = session.coordinator.process_message(envelope)
    except Exception:
        log.exception(
            "coordinator threw on %s from %s", msg_type, sender_principal_id
        )
        return

    rejected = any(
        r.get("message_type") == "PROTOCOL_ERROR" for r in responses
    )

    # Re-broadcast the original message to other participants for types
    # that should be observable (matches reference server behavior).
    if not rejected and msg_type in _BROADCAST_INBOUND_TYPES:
        await _broadcast(session, envelope, exclude=sender_principal_id)

    # Route each coordinator response.
    for resp in responses:
        resp_type = resp.get("message_type", "?")

        if resp_type in _UNICAST_RESPONSE_TYPES:
            await _send_to(session, sender_principal_id, resp)

        elif resp_type == "CONFLICT_REPORT":
            payload = resp.get("payload", {})
            involved = {payload.get("principal_a"), payload.get("principal_b")}
            involved.discard(None)
            for pid in involved:
                await _send_to(session, pid, resp)

        else:
            # SESSION_CLOSE, PARTICIPANT_UPDATE, HEARTBEAT replies, etc.
            await _broadcast(session, resp)


async def _send_to(
    session: ProjectSession, principal_id: str, envelope: Dict[str, Any],
) -> None:
    conn = session.connections.get(principal_id)
    if conn is None:
        return
    try:
        await conn.send(envelope)
    except Exception:
        log.exception(
            "failed sending %s to %s",
            envelope.get("message_type", "?"), principal_id,
        )


async def _broadcast(
    session: ProjectSession,
    envelope: Dict[str, Any],
    exclude: Optional[str] = None,
) -> None:
    targets = [
        p for pid, p in session.connections.items() if pid != exclude
    ]
    if not targets:
        return
    await asyncio.gather(
        *(p.send(envelope) for p in targets),
        return_exceptions=True,
    )


# ── Connection lifecycle helpers ───────────────────────────────────────

async def register_and_hello(
    session: ProjectSession,
    *,
    principal_id: str,
    principal_type: str,
    display_name: str,
    roles: List[str],
    credential_value: str,
    send: Connection,
    is_agent: bool = False,
) -> Optional[_ConnectedParticipant]:
    """Synthesize HELLO on behalf of a newly-connected client + register them.

    Returns the ``_ConnectedParticipant`` on success, ``None`` if HELLO was
    rejected (caller should close the connection).
    """
    # ── Reconnect dedup ─────────────────────────────────────────────
    # If this principal_id already has an active _ConnectedParticipant
    # (e.g. a browser tab that reloaded before its old WebSocket closed,
    # or two tabs for the same user), we need to retire the old one
    # FIRST. Otherwise the coordinator keeps the old participant's
    # intents alive and any file the user re-opens triggers a bogus
    # "Alice ↔ Alice" scope-overlap conflict. Sequence:
    #   1. Synth GOODBYE on the old participant's behalf so the
    #      coordinator drops their intents + presence cleanly.
    #   2. Broadcast offline PARTICIPANT_UPDATE so other tabs/agents
    #      see the transition (the new HELLO below will immediately
    #      re-broadcast online, but that's fine — it's correct state).
    # This happens BEFORE installing the new connection so the HELLO
    # below looks like a fresh join to the coordinator.
    stale = session.connections.get(principal_id)
    if stale is not None:
        log.info(
            "Reconnect detected for %s — retiring stale connection before "
            "accepting new HELLO",
            principal_id,
        )
        try:
            await unregister_and_goodbye(session, stale)
        except Exception:
            log.exception("Failed to retire stale connection %s; continuing",
                          principal_id)

    participant = Participant(
        principal_id=principal_id,
        principal_type=principal_type,
        display_name=display_name,
        roles=roles,
        capabilities=["intent.broadcast", "op.commit"],
        credential={"type": "bearer_token", "value": credential_value},
    )
    conn = _ConnectedParticipant(
        principal_id=principal_id,
        participant=participant,
        send=send,
        display_name=display_name,
        principal_type=principal_type,
        roles=roles,
        is_agent=is_agent,
    )
    # Install connection BEFORE HELLO so the SESSION_INFO response lands.
    session.connections[principal_id] = conn

    hello = participant.hello(session_id=session.mpac_session_id)
    responses = session.coordinator.process_message(hello)

    # Check whether HELLO was accepted (look for CREDENTIAL_REJECTED).
    for r in responses:
        payload = r.get("payload", {})
        if (
            r.get("message_type") == "PROTOCOL_ERROR"
            and payload.get("error_code") == "CREDENTIAL_REJECTED"
        ):
            session.connections.pop(principal_id, None)
            await _send_to(session, principal_id, r)  # notify client first
            log.warning(
                "HELLO rejected for %s: %s",
                principal_id, payload.get("message", "?"),
            )
            return None

    # Dispatch the HELLO responses (SESSION_INFO back, presence broadcast).
    for r in responses:
        resp_type = r.get("message_type", "?")
        if resp_type in _UNICAST_RESPONSE_TYPES:
            await _send_to(session, principal_id, r)
        else:
            await _broadcast(session, r)

    # 1. Tell everyone else "X just joined" — display_name + roles.
    joined_update = _synth_participant_update(
        session.mpac_session_id, conn, status="online",
    )
    await _broadcast(session, joined_update, exclude=principal_id)

    # 2. Send the newcomer a PARTICIPANT_UPDATE for each already-present peer
    #    so it has complete presence state. Include any active_intent_id they
    #    may have so the newcomer immediately sees their file assignments.
    for other_pid, other in session.connections.items():
        if other_pid == principal_id:
            continue
        catchup = _synth_participant_update(
            session.mpac_session_id, other, status="online",
        )
        await _send_to(session, principal_id, catchup)

    log.info(
        "HELLO accepted principal_id=%s project_id=%s type=%s",
        principal_id, session.project_id, principal_type,
    )
    return conn


async def unregister_and_goodbye(
    session: ProjectSession, conn: _ConnectedParticipant,
) -> None:
    """Emit GOODBYE on a client's behalf and drop its connection entry."""
    session.connections.pop(conn.principal_id, None)
    # Bridge-synthesized offline notice so remaining tabs update presence.
    offline = _synth_participant_update(
        session.mpac_session_id, conn, status="offline",
    )
    await _broadcast(session, offline)
    try:
        goodbye = conn.participant.goodbye(session_id=session.mpac_session_id)
        responses = session.coordinator.process_message(goodbye)
    except Exception:
        log.exception("goodbye failed for %s", conn.principal_id)
        return
    for r in responses:
        await _broadcast(session, r)
    log.info("GOODBYE principal_id=%s project_id=%s",
             conn.principal_id, session.project_id)


# ── Helper: load project + membership for a JWT user ──────────────────

@dataclass
class Membership:
    project: Project
    mpac_token: Token


def load_membership(
    db: Session, user_id: int, project_id: int,
) -> Optional[Membership]:
    project = db.get(Project, project_id)
    if not project:
        return None
    token = (
        db.query(Token)
        .filter(
            Token.project_id == project_id,
            Token.user_id == user_id,
            Token.is_revoked == False,  # noqa: E712
        )
        .first()
    )
    if not token:
        return None
    return Membership(project=project, mpac_token=token)
