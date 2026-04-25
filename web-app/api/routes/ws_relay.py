"""The /ws/relay WebSocket: local Claude Code relay ↔ web app backend.

This is the bridge described in Path B variant 2:

  Browser AI chat  →  POST /api/chat  →  [relay_registry.send_chat()]
                                              ↓ ws.send_text
  User's laptop: mpac-mcp-relay listens on this WebSocket
                                              ↓ spawn `claude -p`
                                              ↓ collect reply
                                              ← ws.send_text({"type":"chat_reply", ...})
  [relay_registry resolves the pending Future]
                                              ← HTTP 200 reply
  Browser AI chat renders response.

Additionally, while the relay is connected, the backend registers an MPAC
participant in the project's coordinator session on its behalf — so Claude
appears in WHO'S WORKING on all connected browsers even before any chat
has occurred. On disconnect we GOODBYE + unregister.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Project, Token, User
from ..mpac_bridge import (
    build_verifier_for_project,
    register_and_hello,
    registry as mpac_registry,
    unregister_and_goodbye,
)

log = logging.getLogger("mpac.relay")

router = APIRouter()


# ── In-memory registry ────────────────────────────────────────────────

@dataclass
class _ActiveRelay:
    """One connected relay = one user's Claude on one project."""
    user_id: int
    project_id: int
    display_name: str
    ws: WebSocket
    # Pending chat requests keyed by message_id.  Resolved when the relay
    # sends back a {"type":"chat_reply", "message_id":..., "reply":...}.
    pending: Dict[str, asyncio.Future] = field(default_factory=dict)


class RelayRegistry:
    """Tracks which relays are currently connected, per (user_id, project_id).

    At most one active relay per pair — when a second one arrives the older
    is force-closed (latest-wins matches the token rotation in routes/agent.py).
    """

    def __init__(self) -> None:
        self._by_key: Dict[Tuple[int, int], _ActiveRelay] = {}
        self._lock = asyncio.Lock()

    def is_connected(self, user_id: int, project_id: int) -> bool:
        return (user_id, project_id) in self._by_key

    async def add(self, relay: _ActiveRelay) -> Optional[_ActiveRelay]:
        """Register a relay. Returns the displaced one (caller closes it), if any."""
        key = (relay.user_id, relay.project_id)
        async with self._lock:
            prior = self._by_key.get(key)
            self._by_key[key] = relay
        return prior

    async def remove(self, user_id: int, project_id: int, ws: WebSocket) -> None:
        """Remove iff the currently-registered relay is this ws (idempotent)."""
        key = (user_id, project_id)
        async with self._lock:
            current = self._by_key.get(key)
            if current is not None and current.ws is ws:
                # Cancel any pending chat futures so callers unblock.
                for fut in current.pending.values():
                    if not fut.done():
                        fut.set_exception(RuntimeError("relay disconnected"))
                self._by_key.pop(key, None)

    async def send_chat(self, user_id: int, project_id: int, message: str,
                        timeout: float = 90.0) -> str:
        """Forward a chat message to the user's relay, await the reply.

        Raises:
          LookupError — no relay connected for this (user, project).
          TimeoutError — relay didn't reply within ``timeout`` seconds.
          RuntimeError — relay disconnected mid-request.
        """
        relay = self._by_key.get((user_id, project_id))
        if relay is None:
            raise LookupError("no relay connected")
        message_id = str(uuid.uuid4())
        fut: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        relay.pending[message_id] = fut
        try:
            await relay.ws.send_text(json.dumps({
                "type": "chat",
                "message_id": message_id,
                "message": message,
            }))
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            relay.pending.pop(message_id, None)


relay_registry = RelayRegistry()


# ── WebSocket endpoint ────────────────────────────────────────────────

@router.websocket("/ws/relay/{project_id}")
async def ws_relay(ws: WebSocket, project_id: int, token: str = ""):
    """Relay connects here with ?token=<agent_token>.

    Protocol (JSON text frames):
      Server → client:  {"type":"chat", "message_id":..., "message":"..."}
      Client → server:  {"type":"chat_reply", "message_id":..., "reply":"..."}

    The relay must ALSO send an initial {"type":"hello", "version": "..."}
    within 5 seconds of connecting — we use that to log connection metadata
    and as a cheap liveness check. After hello, the loop is driven by chat
    replies.
    """
    db: Session = SessionLocal()
    displaced_prior: Optional[_ActiveRelay] = None
    relay: Optional[_ActiveRelay] = None
    conn = None  # MPAC participant connection handle
    session = None

    try:
        # ── 1. Authenticate the token ────────────────────────────────
        if not token:
            await ws.close(code=4401, reason="missing token")
            return
        t = db.query(Token).filter(
            Token.token_value == token,
            Token.is_revoked == False,  # noqa: E712
            Token.is_agent == True,  # noqa: E712
            Token.project_id == project_id,
        ).first()
        if t is None:
            await ws.close(code=4401, reason="invalid agent token")
            return
        user = db.get(User, t.user_id)
        project = db.get(Project, project_id)
        if user is None or project is None:
            await ws.close(code=4404, reason="user or project missing")
            return

        await ws.accept()

        # ── 2. Register in the registry (displacing any prior one) ──
        relay = _ActiveRelay(
            user_id=user.id,
            project_id=project_id,
            display_name=f"{user.display_name}'s Claude",
            ws=ws,
        )
        displaced_prior = await relay_registry.add(relay)
        if displaced_prior is not None:
            log.info(
                "Displacing older relay for user=%s project=%s",
                user.id, project_id,
            )
            try:
                await displaced_prior.ws.close(code=4409, reason="superseded")
            except Exception:
                pass

        # ── 3. Join the MPAC session as an agent participant ─────────
        verifier = build_verifier_for_project(db, project_id)
        session = await mpac_registry.get_or_create(
            project_id=project_id,
            mpac_session_id=project.session_id,
            verifier=verifier,
        )
        principal_id = f"agent:user-{user.id}"

        async def send_to_ws(envelope: dict) -> None:
            # Wrap MPAC envelopes so the relay can distinguish them from chat
            # protocol messages. The relay doesn't actually need to do anything
            # with these for MVP — they're for future use (e.g. displaying
            # other participants' intents to Claude).
            await ws.send_text(json.dumps({
                "type": "mpac_envelope",
                "envelope": envelope,
            }))

        async def close_ws(code: int, reason: str) -> None:
            try:
                await ws.close(code=code, reason=reason)
            except Exception:  # noqa: BLE001
                log.debug("relay ws.close failed", exc_info=True)

        conn = await register_and_hello(
            session,
            principal_id=principal_id,
            principal_type="agent",
            display_name=relay.display_name,
            roles=["agent"],
            credential_value=token,
            send=send_to_ws,
            is_agent=True,
            close_ws=close_ws,
        )
        if conn is None:
            await ws.close(code=4403, reason="credential rejected by coordinator")
            return
        log.info(
            "Relay connected: user=%s project=%s display=%r",
            user.id, project_id, relay.display_name,
        )

        # ── 4. Main loop: drive chat replies ─────────────────────────
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Relay sent non-JSON: %r", raw[:200])
                continue
            mtype = msg.get("type")
            if mtype == "hello":
                log.info("Relay hello: version=%r user=%s project=%s",
                         msg.get("version"), user.id, project_id)
            elif mtype == "chat_reply":
                mid = msg.get("message_id")
                reply = msg.get("reply", "")
                fut = relay.pending.get(mid) if mid else None
                if fut is not None and not fut.done():
                    fut.set_result(reply)
                else:
                    log.warning("Orphan chat_reply message_id=%r", mid)
            else:
                log.debug("Relay sent unknown type=%r", mtype)

    except WebSocketDisconnect:
        log.info("Relay disconnected cleanly (user=%s project=%s)",
                 getattr(relay, "user_id", "?"),
                 getattr(relay, "project_id", "?"))
    except Exception as e:
        log.exception("Relay error: %s", e)
    finally:
        if relay is not None:
            await relay_registry.remove(relay.user_id, relay.project_id, ws)
        if session is not None and conn is not None:
            try:
                await unregister_and_goodbye(session, conn)
            except Exception:
                log.exception("Error during agent GOODBYE")
        db.close()
