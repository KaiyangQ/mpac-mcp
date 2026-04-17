"""Project CRUD + invite routes."""
from __future__ import annotations
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Project, Token, Invite, User
from ..schemas import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    InviteCreate, InviteResponse, InviteAccept, InvitePreview, TokenResponse,
)

router = APIRouter()


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    req: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Projects where the user has a live (non-revoked) token
    project_ids = [
        t.project_id for t in db.query(Token).filter(
            Token.user_id == user.id, Token.is_revoked == False  # noqa: E712
        ).all()
    ]
    projects = (
        db.query(Project).filter(Project.id.in_(project_ids)).all()
        if project_ids else []
    )
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
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


@router.get("/invites/{invite_code}", response_model=InvitePreview)
def preview_invite(invite_code: str, db: Session = Depends(get_db)):
    """Public read-only lookup — what project does this invite grant access to?

    Does NOT require authentication: the invite page shows project info before
    the user is asked to log in or register.
    """
    invite = db.query(Invite).filter(Invite.invite_code == invite_code).first()
    if not invite:
        raise HTTPException(404, "Invite not found")
    project = db.get(Project, invite.project_id)
    created_by = db.get(User, invite.created_by_id)
    return InvitePreview(
        invite_code=invite.invite_code,
        project_name=project.name,
        session_id=project.session_id,
        invited_by=created_by.display_name if created_by else "unknown",
        used=invite.used_by_id is not None,
    )


@router.post("/invites/accept", response_model=TokenResponse)
def accept_invite(
    req: InviteAccept,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invite = db.query(Invite).filter(
        Invite.invite_code == req.invite_code,
        Invite.used_by_id == None,  # noqa: E711
    ).first()
    if not invite:
        raise HTTPException(404, "Invite not found or already used")
    # Prevent self-accept (owner already has a token)
    project = db.get(Project, invite.project_id)
    existing = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == invite.project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if existing:
        # Already a member — mark invite used, return their existing token
        invite.used_by_id = user.id
        db.commit()
        return TokenResponse(
            token_value=existing.token_value,
            session_id=project.session_id,
            roles=json.loads(existing.roles),
        )
    # Mark invite as used + create token for the invitee
    invite.used_by_id = user.id
    token = Token(
        token_value=secrets.token_urlsafe(32),
        user_id=user.id,
        project_id=invite.project_id,
        roles=invite.roles,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return TokenResponse(
        token_value=token.token_value,
        session_id=project.session_id,
        roles=json.loads(token.roles),
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch a single project by id. User must have a live token on it."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    membership = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not membership:
        raise HTTPException(403, "You are not a member of this project")
    return ProjectResponse(
        id=project.id,
        session_id=project.session_id,
        name=project.name,
        owner_id=project.owner_id,
        created_at=project.created_at.isoformat(),
    )
