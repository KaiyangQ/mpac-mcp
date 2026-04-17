"""MPAC Web App — FastAPI backend."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

# Configure logging so our own `logging.getLogger("mpac.*")` calls render
# alongside uvicorn's access log. Uvicorn doesn't set up the root logger,
# so we do it here at import time.
logging.basicConfig(
    level=os.environ.get("MPAC_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .auth import decode_jwt
from .database import SessionLocal, init_db, get_db
from .mpac_bridge import (
    browser_action_to_envelope,
    build_verifier_for_project,
    load_membership,
    process_envelope,
    register_and_hello,
    registry,
    unregister_and_goodbye,
)
from .models import User

log = logging.getLogger("mpac.web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="MPAC Web App API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server (any localhost port in dev) and prod frontend
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_origins=[
        "https://mpac-web.fly.dev",
        "https://mpac-web.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from .routes import users, projects, tokens, chat  # noqa: E402

app.include_router(users.router, prefix="/api", tags=["auth"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(tokens.router, prefix="/api", tags=["tokens"])
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── WebSocket: Browser ↔ MPAC coordinator bridge ─────────────────────

@app.websocket("/ws/session/{project_id}")
async def ws_session(ws: WebSocket, project_id: int, token: str = ""):
    """Bridge a browser to this project's in-process MPAC coordinator.

    Auth: JWT passed via `?token=` query param (WebSocket handshake can't
    send custom headers reliably from the browser). We then look up the
    user's MPAC bearer token in our DB and synthesize a HELLO on their
    behalf.

    Browser protocol:
      - Sends JSON actions: ``{"action": "begin_task", ...}`` etc.
        (see ``browser_action_to_envelope`` for the vocabulary).
      - Receives raw MPAC envelopes — frontend matches on ``message_type``.
    """
    # 1. JWT → user
    payload = decode_jwt(token) if token else None
    if not payload:
        await ws.close(code=4401, reason="invalid token")
        return

    # We use a short-lived DB session for lookup + the verifier closure.
    # Holding it for the whole WS lifetime is fine in dev (SQLite); we'll
    # revisit when we move to Postgres.
    db: Session = SessionLocal()
    try:
        user = db.get(User, int(payload["sub"]))
        if not user:
            await ws.close(code=4401, reason="user not found")
            return

        membership = load_membership(db, user.id, project_id)
        if not membership:
            await ws.close(code=4403, reason="not a member of this project")
            return

        verifier = build_verifier_for_project(db, project_id)
        session = await registry.get_or_create(
            project_id=project_id,
            mpac_session_id=membership.project.session_id,
            verifier=verifier,
        )

        await ws.accept()
        principal_id = f"user:{user.id}"

        import json as _json

        async def send_to_ws(envelope: dict) -> None:
            # WebSocket.send_json uses jsonable_encoder which chokes on our
            # plain dicts containing datetimes already stringified; use raw
            # send_text with json.dumps to keep full control.
            await ws.send_text(_json.dumps(envelope, ensure_ascii=False))

        conn = await register_and_hello(
            session,
            principal_id=principal_id,
            principal_type="human",
            display_name=user.display_name,
            roles=_safe_roles(membership.mpac_token.roles),
            credential_value=membership.mpac_token.token_value,
            send=send_to_ws,
            is_agent=False,
        )
        if conn is None:
            await ws.close(code=4403, reason="credential rejected")
            return

        try:
            while True:
                raw = await ws.receive_text()
                try:
                    action = _json.loads(raw)
                except _json.JSONDecodeError:
                    continue
                envelope = browser_action_to_envelope(
                    action, conn.participant, session.mpac_session_id,
                )
                if envelope is None:
                    continue
                await process_envelope(session, envelope, principal_id)

        except WebSocketDisconnect:
            pass
        finally:
            await unregister_and_goodbye(session, conn)

    finally:
        db.close()


def _safe_roles(raw: str | None) -> list[str]:
    import json as _json
    if not raw:
        return ["contributor"]
    try:
        roles = _json.loads(raw)
        return roles if isinstance(roles, list) else ["contributor"]
    except _json.JSONDecodeError:
        return ["contributor"]
