"""Project CRUD + invite routes."""
from __future__ import annotations
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import decode_jwt
from ..database import get_db
from ..models import Project, Token, Invite, User
from ..schemas import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    InviteCreate, InviteResponse, InviteAccept, TokenResponse,
)

router = APIRouter()


def _get_current_user(db: Session, authorization: str) -> User:
    """Extract user from Authorization: Bearer <jwt> header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    payload = decode_jwt(authorization[7:])
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    user = db.query(User).get(int(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    req: ProjectCreate,
    authorization: str = "",
    db: Session = Depends(get_db),
):
    user = _get_current_user(db, authorization)
    session_id = f"proj-{secrets.token_hex(8)}"
    project = Project(session_id=session_id, name=req.name, owner_id=user.id)
    db.add(project)
    db.flush()
    # Auto-create a token for the owner
    token = Token(
        token_value=secrets.token_urlsafe(32),
        user_id=user.id,
        project_id=project.id,
        roles=json.dumps(["owner"]),
    )
    db.add(token)
    db.commit()
    db.refresh(project)
    return ProjectResponse(
        id=project.id,
        session_id=project.session_id,
        name=project.name,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
    )


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(authorization: str = "", db: Session = Depends(get_db)):
    user = _get_current_user(db, authorization)
    # Projects where user has a token
    project_ids = [t.project_id for t in db.query(Token).filter(Token.user_id == user.id, Token.is_revoked == False).all()]
    projects = db.query(Project).filter(Project.id.in_(project_ids)).all() if project_ids else []
    return ProjectListResponse(projects=[
        ProjectResponse(
            id=p.id, session_id=p.session_id, name=p.name,
            owner_id=p.owner_id, created_at=p.created_at.isoformat(),
        ) for p in projects
    ])


@router.post("/projects/{project_id}/invite", response_model=InviteResponse)
def create_invite(
    project_id: int,
    req: InviteCreate,
    authorization: str = "",
    db: Session = Depends(get_db),
):
    user = _get_current_user(db, authorization)
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "Only the project owner can create invites")
    invite = Invite(
        invite_code=secrets.token_urlsafe(16),
        project_id=project.id,
        created_by_id=user.id,
        roles=json.dumps(req.roles),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return InviteResponse(
        invite_code=invite.invite_code,
        project_name=project.name,
        session_id=project.session_id,
    )


@router.post("/invites/accept", response_model=TokenResponse)
def accept_invite(
    req: InviteAccept,
    authorization: str = "",
    db: Session = Depends(get_db),
):
    user = _get_current_user(db, authorization)
    invite = db.query(Invite).filter(Invite.invite_code == req.invite_code, Invite.used_by_id == None).first()
    if not invite:
        raise HTTPException(404, "Invite not found or already used")
    # Mark invite as used
    invite.used_by_id = user.id
    # Create token for the invitee
    token = Token(
        token_value=secrets.token_urlsafe(32),
        user_id=user.id,
        project_id=invite.project_id,
        roles=invite.roles,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    project = db.query(Project).get(invite.project_id)
    return TokenResponse(
        token_value=token.token_value,
        session_id=project.session_id,
        roles=json.loads(token.roles),
    )
