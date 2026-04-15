"""MPAC token retrieval route."""
from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Token, Project, User
from ..schemas import TokenResponse
from .projects import _get_current_user

router = APIRouter()


@router.get("/projects/{project_id}/token", response_model=TokenResponse)
def get_my_token(
    project_id: int,
    authorization: str = "",
    db: Session = Depends(get_db),
):
    """Get the current user's MPAC bearer token for a project."""
    user = _get_current_user(db, authorization)
    token = (
        db.query(Token)
        .filter(
            Token.project_id == project_id,
            Token.user_id == user.id,
            Token.is_revoked == False,
        )
        .first()
    )
    if not token:
        raise HTTPException(404, "No token found for this project — accept an invite first")
    project = db.query(Project).get(project_id)
    return TokenResponse(
        token_value=token.token_value,
        session_id=project.session_id,
        roles=json.loads(token.roles),
    )
