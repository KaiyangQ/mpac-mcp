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
from .config import ALLOWED_ORIGINS, INVITE_CODES, IS_PRODUCTION
from .database import SessionLocal, init_db, get_db
from .models import SignupCode, User
from .mpac_bridge import (
    browser_action_to_envelope,
    build_verifier_for_project,
    load_membership,
    process_envelope,
    register_and_hello,
    registry,
    unregister_and_goodbye,
)

log = logging.getLogger("mpac.web")


def _seed_signup_codes() -> None:
    """Insert configured invite codes that don't yet exist in the DB.

    We never delete rows here — a code that's been burned (used_by_id set)
    must stay in the DB even if it's dropped from the env var, so a redeploy
    can't accidentally resurrect it. Similarly, we don't touch `used_by_id`
    on existing rows, so reseeding is idempotent.
    """
    if not INVITE_CODES:
        return
    db = SessionLocal()
    try:
        existing = {
            row.code for row in db.query(SignupCode).filter(
                SignupCode.code.in_(INVITE_CODES)
            ).all()
        }
        inserted = 0
        for code in INVITE_CODES:
            if code not in existing:
                db.add(SignupCode(code=code))
                inserted += 1
        if inserted:
            db.commit()
            log.info("Seeded %d new signup code(s); %d already present",
                     inserted, len(existing))
        else:
            log.info("Signup codes already seeded (%d in DB)", len(existing))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup + seed signup codes."""
    init_db()
    _seed_signup_codes()
    yield


app = FastAPI(
    title="MPAC Web App API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — dev allows any localhost port; prod reads an explicit allowlist
# from MPAC_WEB_ALLOWED_ORIGINS. We keep `allow_credentials=True` because
# the future cookie-based refresh flow needs it; today's JWT-in-localStorage
# setup works either way.
if IS_PRODUCTION:
    if not ALLOWED_ORIGINS:
        log.warning(
            "MPAC_WEB_ALLOWED_ORIGINS is empty in production — all browsers "
            "will be refused by CORS. Set it to the deployed frontend URL."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
        # Extra prod-style origins allowed in dev too, so a local API + hosted
        # frontend combo works for smoke-testing.
        allow_origins=ALLOWED_ORIGINS or [
            "https://mpac-web-app.fly.dev",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Import and include routers
from .routes import users, projects, tokens, chat, settings, files, agent, ws_relay  # noqa: E402

app.include_router(users.router, prefix="/api", tags=["auth"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(tokens.router, prefix="/api", tags=["tokens"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
# ws_relay owns /ws/relay/{project_id} — mounted at root (no /api prefix,
# matches the /ws/session pattern below).
app.include_router(ws_relay.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── WebSocket: Browser ↔ MPAC coordinator bridge ─────────────────────

def _origin_allowed(origin: str | None) -> bool:
    """Check a WebSocket upgrade's Origin header against our CORS allowlist.

    Browsers send ``Origin`` on WS handshakes but the server has to validate
    it explicitly — FastAPI/Starlette's ``CORSMiddleware`` only covers HTTP.
    In dev we accept missing origin (curl / wscat) so local manual testing
    keeps working.
    """
    if not origin:
        return not IS_PRODUCTION
    if origin in ALLOWED_ORIGINS:
        return True
    if not IS_PRODUCTION and (
        origin.startswith("http://localhost:")
        or origin.startswith("http://127.0.0.1:")
    ):
        return True
    return False


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
    # 0. Origin pin — reject cross-site WebSocket attempts before doing any work.
    origin = ws.headers.get("origin") or ws.headers.get("Origin")
    if not _origin_allowed(origin):
        log.warning("Rejecting WS handshake from disallowed origin=%r", origin)
        await ws.close(code=4403, reason="origin not allowed")
        return

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

        async def close_ws(code: int, reason: str) -> None:
            # Used by force_close_project_session on project delete so this
            # browser tab gets booted instead of holding a stale view.
            try:
                await ws.close(code=code, reason=reason)
            except Exception:  # noqa: BLE001
                log.debug("ws.close failed (already closed?)", exc_info=True)

        conn = await register_and_hello(
            session,
            principal_id=principal_id,
            principal_type="human",
            display_name=user.display_name,
            roles=_safe_roles(membership.mpac_token.roles),
            credential_value=membership.mpac_token.token_value,
            send=send_to_ws,
            is_agent=False,
            close_ws=close_ws,
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
                    db=db, project_id=session.project_id,
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
