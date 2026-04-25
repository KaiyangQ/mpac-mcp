"""MPAC token retrieval route."""
from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Project, Token, User
from ..schemas import TokenResponse

router = APIRouter()


@router.get("/projects/{project_id}/token", response_model=TokenResponse)
def get_my_token(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's MPAC bearer token for the given project."""
    token = (
        db.query(Token)
        .filter(
            Token.project_id == project_id,
            Token.user_id == user.id,
            Token.is_revoked == False,  # noqa: E712
        )
        .first()
    )
    if not token:
        raise HTTPException(
            404,
            "No token found for this project — accept an invite first",
        )
    project = db.get(Project, project_id)
    return TokenResponse(
        session_id=project.session_id,
        roles=json.loads(token.roles),
    )
