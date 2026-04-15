"""AI chat route — Claude API + MPAC agent integration (Phase E stub)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..schemas import ChatMessage

router = APIRouter()


@router.post("/chat")
async def chat(msg: ChatMessage):
    """Phase E: will stream Claude response + trigger MPAC agent actions.

    For now returns a stub so the app can boot without errors.
    """
    return JSONResponse(
        {"reply": "[AI chat not yet connected — Phase E]", "agent_actions": []},
        status_code=200,
    )
