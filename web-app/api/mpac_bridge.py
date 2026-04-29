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

from mpac_protocol.analysis import scan_reverse_deps, scan_reverse_deps_detailed
from mpac_protocol.core.coordinator import (
    CredentialVerifier,
    SessionCoordinator,
    VerifyResult,
)
from mpac_protocol.core.models import Scope
from mpac_protocol.core.participant import Participant
from sqlalchemy.orm import Session

from .models import Project, ProjectFile, Token

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
    "INTENT_DEFERRED",
    "CONFLICT_ACK", "CONFLICT_ESCALATE", "RESOLUTION",
})

# Outbound response types that go ONLY to the original sender.
_UNICAST_RESPONSE_TYPES = frozenset({
    "PROTOCOL_ERROR", "SESSION_INFO", "OP_REJECT", "INTENT_CLAIM_STATUS",
})


def _synth_project_event_envelope(
    session_id: str,
    kind: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a bridge-synthesized PROJECT_EVENT envelope.

    PROJECT_EVENT is a non-MPAC-spec wrapper used to notify all browsers in
    a session about backend-side state changes that aren't part of the core
    coordination protocol — e.g. a file was overwritten via the HTTP file
    API, the project was deleted, the owner clicked "Reset to seed".
    Frontends switch on ``payload.kind`` to decide what to refresh.

    Kinds currently in use:
      * ``file_changed`` — payload also has ``path``, ``updated_at``
      * ``file_deleted`` — payload also has ``path``
      * ``reset_to_seed`` — file tree should be re-fetched wholesale
      * ``project_deleted`` — frontend should redirect to /projects
    """
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {"kind": kind, **payload}
    return {
        "protocol": "MPAC",
        "version": "0.1.13",
        "message_type": "PROJECT_EVENT",
        "message_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sender": {
            "principal_id": f"service:bridge-{session_id}",
            "principal_type": "coordinator",
            "sender_instance_id": f"service:bridge-{session_id}",
        },
        "ts": now,
        "payload": body,
    }


def _co_principal_for_owner(principal_id: Optional[str]) -> Optional[str]:
    """Map a principal_id to its sibling for the same human owner.

    Two surfaces represent one human:
      * ``user:N``        — the browser session WS (routes/main.py)
      * ``agent:user-N``  — the Claude relay WS    (routes/ws_relay.py)

    Returns the sibling form, or ``None`` if the principal_id doesn't
    follow either pattern (e.g. service principals, future shapes).
    Used by CONFLICT_REPORT routing so a conflict between two agents
    also reaches each agent's owning browser tab.
    """
    if not principal_id:
        return None
    if principal_id.startswith("agent:user-"):
        return f"user:{principal_id[len('agent:user-'):]}"
    if principal_id.startswith("user:"):
        return f"agent:user-{principal_id[len('user:'):]}"
    return None


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
    # Optional ws-close callback so the bridge can force-close the underlying
    # WebSocket on project_deleted / kick. Browser handlers (ws_session) and
    # the relay handler (ws_relay) install this when they accept a socket.
    # ``None`` means "the producer didn't expose a close hook" — broadcast
    # still works, just no force-close.
    close_ws: Optional[Callable[[int, str], Awaitable[None]]] = None


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
        # Captured on first async entry; sync routes use this to schedule
        # broadcast coroutines onto the right loop via run_coroutine_threadsafe.
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _capture_loop(self) -> None:
        """Stash the running event loop the first time we see one. Called
        from async paths (get_or_create, the WS handlers) so the sync HTTP
        routes can later schedule broadcasts without re-creating a loop."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                pass  # No loop yet — sync init context; will retry next call.

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._loop

    async def get_or_create(
        self,
        project_id: int,
        mpac_session_id: str,
        verifier: CredentialVerifier,
    ) -> ProjectSession:
        self._capture_loop()
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

    def drop(self, project_id: int) -> bool:
        """Remove the in-memory session for ``project_id`` — called when
        the project is deleted in the DB. Any live WS clients still
        connected will operate against the stale reference until they
        disconnect, which is fine: they can't reconnect because the
        membership check on ``/ws/session`` will fail once the tokens
        are gone. Returns True if a session was present and dropped.
        """
        existed = project_id in self._sessions
        self._sessions.pop(project_id, None)
        if existed:
            log.info("Dropped MPAC session for deleted project_id=%s", project_id)
        return existed


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


# ── Cross-file impact analysis ────────────────────────────────────────
# v0.2.1 added file-level dependency_breakage detection.
# v0.2.2 adds per-importer symbol detail so Alice's "I'm only touching
# utils.foo" can disjoint Bob's "main.py uses utils.bar" — no more false
# positive when the dependency exists but the specific symbols don't clash.

def _load_project_py_sources(
    db: Session, project_id: int,
) -> Dict[str, str]:
    """Pull every .py file for this project out of the DB into an
    in-memory {path: content} map for the analyzer. Single query, one
    fetch per announce — worth optimizing if load tests show this
    dominating."""
    rows = (
        db.query(ProjectFile.path, ProjectFile.content)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.path.like("%.py"),
        )
        .all()
    )
    return {path: content or "" for (path, content) in rows}


def compute_scope_impact(
    db: Session, project_id: int, files: List[str],
) -> List[str]:
    """Return the set of OTHER files in the project that statically import
    from any of ``files``. **v0.2.1-compatible** — file list only.

    Prefer :func:`compute_scope_impact_detailed` in new code; it returns
    the same file set plus per-file symbol data the v0.2.2 coordinator
    uses to skip false positives.
    """
    if not files:
        return []
    try:
        sources = _load_project_py_sources(db, project_id)
        return scan_reverse_deps(files, sources)
    except Exception:  # noqa: BLE001
        log.exception(
            "compute_scope_impact failed (project_id=%s, files=%s) — "
            "falling back to empty impact",
            project_id, files,
        )
        return []


def compute_scope_impact_detailed(
    db: Session, project_id: int, files: List[str],
) -> Dict[str, Optional[List[str]]]:
    """v0.2.2: return {importer_file: [symbols_used] | None} for every
    file that imports from ``files``. ``None`` as the value means the
    importer did a bare ``import X`` or ``from X import *`` — callers
    must treat as "any symbol could be touched" (wildcard fallback).

    Empty dict on any failure — graceful degradation matches 0.2.1.
    """
    if not files:
        return {}
    try:
        sources = _load_project_py_sources(db, project_id)
        return scan_reverse_deps_detailed(files, sources)
    except Exception:  # noqa: BLE001
        log.exception(
            "compute_scope_impact_detailed failed (project_id=%s, files=%s) — "
            "falling back to empty impact",
            project_id, files,
        )
        return {}


def build_file_scope(
    files: List[str],
    *,
    db: Optional[Session] = None,
    project_id: Optional[int] = None,
    affects_symbols: Optional[List[str]] = None,
) -> Scope:
    """Construct a ``file_set`` Scope.

    When ``db`` + ``project_id`` are provided (normal web-app path), the
    scope is enriched with:

    * ``extensions.impact`` — v0.2.1 file list (kept for old-coordinator
      compatibility). Always populated when impact exists.
    * ``extensions.impact_symbols`` — v0.2.2 per-file symbol map. Always
      populated alongside ``impact`` when detailed scanning succeeds.
    * ``extensions.affects_symbols`` — v0.2.2 agent-declared set of
      symbols actually being modified. Populated only when
      ``affects_symbols`` is passed. Without it the coordinator falls
      back to file-level "assume all symbols touched".

    Callers without a DB handle (tests, degraded flows) get a plain
    file-path scope — equivalent to v0.2.0 behavior.
    """
    scope = Scope(kind="file_set", resources=list(files))
    ext: Dict[str, Any] = {}

    if db is not None and project_id is not None:
        detail = compute_scope_impact_detailed(db, project_id, files)
        if detail:
            # Keep ``impact`` as the stable v0.2.1-compatible file list
            # so a mixed-version fleet still reads it.
            ext["impact"] = sorted(detail.keys())
            ext["impact_symbols"] = detail

    if affects_symbols:
        # Dedup + drop blanks; preserve stable order for test determinism
        seen = set()
        cleaned: List[str] = []
        for s in affects_symbols:
            if s and isinstance(s, str) and s not in seen:
                seen.add(s)
                cleaned.append(s)
        if cleaned:
            ext["affects_symbols"] = cleaned

    if ext:
        scope.extensions = ext
    return scope


# ── Simplified browser action → MPAC envelope ──────────────────────────

def browser_action_to_envelope(
    action: Dict[str, Any],
    participant: Participant,
    session_id: str,
    *,
    db: Optional[Session] = None,
    project_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Translate a tiny browser action vocabulary into an MPAC envelope.

    Returns ``None`` for unknown actions (the caller should drop them).

    ``db`` + ``project_id`` are optional so the function stays usable from
    thin contexts, but when both are provided, ``begin_task`` gets a
    cross-file impact set attached to its scope (enables dependency_breakage
    detection downstream).
    """
    kind = action.get("action")

    if kind == "begin_task":
        files = action.get("files") or []
        intent_id = action.get("intent_id") or f"intent-{uuid.uuid4().hex[:12]}"
        objective = action.get("objective") or "editing"
        # v0.2.2: browser can optionally declare which symbols will be
        # touched; if absent, coordinator falls back to file-level.
        raw_symbols = action.get("symbols")
        affects_symbols = raw_symbols if isinstance(raw_symbols, list) else None
        scope = build_file_scope(
            list(files),
            db=db, project_id=project_id,
            affects_symbols=affects_symbols,
        )
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
) -> List[Dict[str, Any]]:
    """Feed an envelope through the coordinator and route responses.

    Mirrors `MPACServer.handler` logic. Exceptions are logged and swallowed —
    a misbehaving client shouldn't take down the session.

    Returns the list of envelopes the coordinator emitted in response
    (empty on exception). Older callers ignore the return value; the
    HTTP-side announce_intent endpoint inspects it to surface
    STALE_INTENT (v0.2.8 race lock) and same-tick CONFLICT_REPORT
    (dependency_breakage warnings) back to the agent.
    """
    msg_type = envelope.get("message_type", "?")
    try:
        responses = session.coordinator.process_message(envelope)
    except Exception:
        log.exception(
            "coordinator threw on %s from %s", msg_type, sender_principal_id
        )
        return []

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
            # In the real product flow both intents come from agent relays
            # (Claude does the editing), so principal_a/b are ``agent:user-N``.
            # Unicasting only to those two skips the human's browser tab
            # (``user:N``) — the Conflicts panel never renders even though
            # the chat board shows the peer agent's intent. Mirror the
            # routing across the agent↔user pair so both surfaces light up.
            for pid in list(involved):
                involved.add(_co_principal_for_owner(pid))
            involved.discard(None)
            for pid in involved:
                await _send_to(session, pid, resp)

        else:
            # SESSION_CLOSE, PARTICIPANT_UPDATE, HEARTBEAT replies, etc.
            await _broadcast(session, resp)

    return responses


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


async def force_close_project_session(
    project_id: int,
    *,
    code: int = 4404,
    reason: str = "project deleted",
) -> None:
    """Boot every WebSocket bound to ``project_id`` and clear coordinator
    state. Used by ``DELETE /api/projects/{id}`` so other open browsers
    don't keep editing a project that's already gone from the DB.

    Sequence per connection:
      1. Call its ``close_ws(code, reason)`` callback if installed; that
         goes through FastAPI's normal WS teardown so the upstream handler's
         ``finally:`` block runs (cleanup, log, etc.).
      2. Connections without a ``close_ws`` (e.g. test stubs) just get
         dropped from the registry; their next ``send`` will fail and the
         underlying socket — if any — will time out naturally.

    Always followed by ``registry.drop(project_id)``; we don't drop here
    because the caller may want to broadcast a final envelope first.
    """
    session = registry.get(project_id)
    if session is None:
        return
    conns = list(session.connections.values())
    session.connections.clear()
    for c in conns:
        if c.close_ws is None:
            continue
        try:
            await c.close_ws(code, reason)
        except Exception:
            log.exception(
                "force_close: failed to close ws for principal_id=%s",
                c.principal_id,
            )


def force_close_project_session_sync(
    project_id: int, *, code: int = 4404, reason: str = "project deleted",
) -> None:
    """Sync wrapper around :func:`force_close_project_session` so HTTP
    routes can call it without ``await``. Schedules onto the bridge's
    captured event loop and returns immediately. If no loop is captured
    (no WS has ever connected), there's nothing to close — silently no-op.
    """
    loop = registry.loop
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(
            force_close_project_session(project_id, code=code, reason=reason),
            loop,
        )
    except RuntimeError:
        log.exception(
            "force_close_project_session_sync: scheduling failed "
            "(project_id=%s)", project_id,
        )


def force_close_principals_sync(
    project_id: int,
    principal_ids: List[str],
    *,
    code: int = 4403,
    reason: str = "membership revoked",
) -> None:
    """Force-close just the listed principals' WebSockets in a project,
    leaving everyone else connected. Used by ``POST /projects/{id}/leave``
    so a leaving user's browser/relay get booted while remaining members
    keep their sessions alive.

    Schedules onto the captured event loop and returns immediately. No-op
    if no loop or no live session.
    """
    session = registry.get(project_id)
    if session is None:
        return
    loop = registry.loop
    if loop is None or loop.is_closed():
        # Best-effort: drop coordinator state for the listed principals so
        # they're at least gone from in-memory presence, even though we
        # can't actually close their sockets without a loop.
        for pid in principal_ids:
            session.connections.pop(pid, None)
        return

    async def _run() -> None:
        for pid in principal_ids:
            conn = session.connections.pop(pid, None)
            if conn is None or conn.close_ws is None:
                continue
            try:
                await conn.close_ws(code, reason)
            except Exception:
                log.exception(
                    "force_close_principals: close_ws failed for %s", pid,
                )

    try:
        asyncio.run_coroutine_threadsafe(_run(), loop)
    except RuntimeError:
        log.exception(
            "force_close_principals_sync: scheduling failed "
            "(project_id=%s)", project_id,
        )


def lifecycle_delete_sync(
    project_id: int,
    project_name: str,
) -> None:
    """Atomic project-deletion lifecycle: broadcast PROJECT_EVENT, then
    force-close every WS, then drop the in-memory session — all on the
    captured event loop, in that order, in a single coroutine.

    Why one coroutine instead of three sync calls: ``_broadcast`` and
    ``force_close_project_session`` both ``await`` internally, so if we
    scheduled them as separate coroutines via ``run_coroutine_threadsafe``
    the loop could interleave them — close runs first, broadcast finds
    an empty connections dict, no envelope arrives. Bundling guarantees
    the broadcast lands before any socket gets closed.

    No-ops cleanly when no live session exists for the project (e.g. the
    project never had a WS client) — the DB cascade in the caller has
    already done the durable work; there's just nothing in-memory to
    notify.
    """
    session = registry.get(project_id)
    if session is None:
        return
    loop = registry.loop
    if loop is None or loop.is_closed():
        # No loop = nothing's ever awaited on this process. The session
        # entry exists but has no live connections. Drop it directly.
        registry.drop(project_id)
        return

    async def _run() -> None:
        envelope = _synth_project_event_envelope(
            session.mpac_session_id,
            "project_deleted",
            {"project_id": project_id, "project_name": project_name},
        )
        try:
            await _broadcast(session, envelope)
        except Exception:
            log.exception("lifecycle_delete: broadcast failed (project_id=%s)",
                          project_id)
        # Close every connected ws so the next thing each client sees is the
        # close frame, not a stale envelope on a half-dead session.
        conns = list(session.connections.values())
        session.connections.clear()
        for c in conns:
            if c.close_ws is None:
                continue
            try:
                await c.close_ws(4404, "project deleted")
            except Exception:
                log.exception(
                    "lifecycle_delete: close_ws failed for %s",
                    c.principal_id,
                )
        registry.drop(project_id)

    try:
        asyncio.run_coroutine_threadsafe(_run(), loop)
    except RuntimeError:
        log.exception(
            "lifecycle_delete_sync: scheduling failed (project_id=%s)",
            project_id,
        )


# ── Project-event broadcast (HTTP routes → WS clients) ─────────────────

def broadcast_project_event(
    project_id: int,
    kind: str,
    payload: Dict[str, Any],
    *,
    exclude_principal: Optional[str] = None,
) -> None:
    """Notify every browser/relay in the project's session about a backend
    state change that originated from a sync HTTP route.

    Sync routes can't ``await`` so we schedule the actual fan-out onto the
    bridge's captured event loop via :func:`asyncio.run_coroutine_threadsafe`.
    Loop reference is captured on the first async entry to the registry; if
    no WS has ever connected for any project, ``registry.loop`` is ``None``
    and we silently no-op (there's nobody to notify anyway).

    Returns immediately — this is fire-and-forget. Failures are logged on
    the loop's side via :func:`_broadcast`'s ``return_exceptions=True``.

    See :func:`_synth_project_event_envelope` for the kinds currently in
    use (``file_changed``, ``file_deleted``, ``reset_to_seed``,
    ``project_deleted``).
    """
    session = registry.get(project_id)
    if session is None:
        return
    loop = registry.loop
    if loop is None or loop.is_closed():
        log.debug(
            "broadcast_project_event: no event loop captured yet "
            "(project_id=%s, kind=%s) — skipping", project_id, kind,
        )
        return
    envelope = _synth_project_event_envelope(
        session.mpac_session_id, kind, payload,
    )
    coro = _broadcast(session, envelope, exclude=exclude_principal)
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except RuntimeError:
        log.exception(
            "broadcast_project_event: failed to schedule fan-out "
            "(project_id=%s, kind=%s)", project_id, kind,
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
    close_ws: Optional[Callable[[int, str], Awaitable[None]]] = None,
) -> Optional[_ConnectedParticipant]:
    """Synthesize HELLO on behalf of a newly-connected client + register them.

    Returns the ``_ConnectedParticipant`` on success, ``None`` if HELLO was
    rejected (caller should close the connection).

    ``close_ws`` is an optional callback the bridge can invoke to force-close
    the underlying WebSocket — used by :func:`force_close_project_session` so
    project deletion can immediately kick everyone out instead of leaving
    them on a stale registry entry. Browser/relay handlers should pass a
    wrapper around their ``ws.close(code, reason)`` so the close goes through
    FastAPI's normal teardown path.
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
        close_ws=close_ws,
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
