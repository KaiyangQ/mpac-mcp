"""AI chat route — spawns a Claude agent that joins the MPAC session as a peer."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..agent.claude_agent import ClaudeAgent
from ..auth import get_current_user
from ..database import get_db
from ..models import Project, Token, User
from ..mpac_bridge import registry
from ..schemas import ChatMessage, ChatReply

router = APIRouter()


@router.post("/chat", response_model=ChatReply)
async def chat(
    msg: ChatMessage,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run one agent turn for the user's chat message.

    The agent joins the project's MPAC session (visible in the collaboration
    panel), announces an intent on the files it plans to edit, waits briefly
    to simulate work, withdraws, and leaves. Returns the assistant's text
    reply — no streaming for MVP.
    """
    # Membership check: only members of the project may spawn the agent.
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

    agent = ClaudeAgent(project=project, registry=registry, db=db)
    reply = await agent.run(msg.message)
    return ChatReply(reply=reply)
