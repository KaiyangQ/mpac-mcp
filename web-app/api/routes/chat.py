"""AI chat route — routes to the user's local Claude Code relay if connected,
falls back to BYOK ClaudeAgent otherwise.

Routing priority (Path B variant 2):
  1. Relay online for (user, project) → forward the message to the user's
     mpac-mcp-relay process; it spawns `claude -p` locally and returns the
     reply. Uses the user's Claude Code subscription, not an API key.
  2. BYOK Anthropic key on file → existing ClaudeAgent path (API-keyed).
  3. In production without either → 402 prompting the user to either start
     the relay or add an API key. In dev we still let ClaudeAgent's canned
     fallback produce a demo reply so the UI keeps working offline.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agent.claude_agent import ClaudeAgent
from ..auth import get_current_user
from ..config import ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, IS_PRODUCTION
from ..crypto import decrypt_str
from ..database import get_db
from ..models import Project, Token, User
from ..mpac_bridge import registry
from ..schemas import ChatMessage, ChatReply
from .ws_relay import relay_registry

router = APIRouter()
log = logging.getLogger("mpac.chat")


@router.post("/chat", response_model=ChatReply)
async def chat(
    msg: ChatMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Membership check: only members of the project may chat.
    project = db.get(Project, msg.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    membership = (
        db.query(Token)
        .filter(
            Token.project_id == msg.project_id,
            Token.user_id == user.id,
            Token.is_revoked == False,  # noqa: E712
        )
        .first()
    )
    if not membership:
        raise HTTPException(403, "You are not a member of this project")

    # ── Route 1: relay is connected ──────────────────────────────────
    if relay_registry.is_connected(user.id, msg.project_id):
        log.info("Chat via relay: user=%s project=%s", user.id, msg.project_id)
        try:
            reply = await relay_registry.send_chat(
                user.id, msg.project_id, msg.message,
            )
            return ChatReply(reply=reply)
        except TimeoutError:
            raise HTTPException(504, "Local Claude Code timed out (>90s)")
        except LookupError:
            # Relay raced-disconnected between is_connected() and send_chat();
            # fall through to BYOK path.
            log.warning("Relay disappeared mid-request, falling back to BYOK")
        except RuntimeError as e:
            # Relay disconnected during the request.
            raise HTTPException(503, f"Local Claude Code relay dropped: {e}")

    # ── Route 2: BYOK fallback ───────────────────────────────────────
    user_api_key: str | None = None
    if user.anthropic_api_key_encrypted:
        user_api_key = decrypt_str(user.anthropic_api_key_encrypted)

    if IS_PRODUCTION and not user_api_key:
        raise HTTPException(
            status_code=402,
            detail=(
                "Chat needs either a running Claude Code relay "
                "(click Connect Claude) or an Anthropic API key "
                "(Settings → Anthropic API key)."
            ),
        )

    log.info("Chat via BYOK: user=%s project=%s has_key=%s",
             user.id, msg.project_id, user_api_key is not None)
    agent = ClaudeAgent(
        project=project, registry=registry, db=db, api_key=user_api_key,
    )
    reply = await agent.run(msg.message)
    return ChatReply(reply=reply)


# Silence unused-import lints — we reference them for the dev fallback path
# via `config.IS_PRODUCTION`, not directly. Keeping the imports makes it obvious
# which knobs control the BYOK vs platform-key behaviour.
_ = (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN)
