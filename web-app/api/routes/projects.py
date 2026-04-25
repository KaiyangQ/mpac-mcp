"""Project CRUD + invite routes."""
from __future__ import annotations
import json
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Project, ProjectFile, Token, Invite, User
from ..mpac_bridge import registry as session_registry
from ..schemas import (
    ProjectCreate, ProjectResponse, ProjectListResponse,
    InviteCreate, InviteResponse, InviteAccept, InvitePreview, TokenResponse,
)
from ..seed_data.notes_app import FILES as NOTES_APP_SEED


log = logging.getLogger("mpac.projects")

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


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Destroy the project for everyone — owner only.

    Cascades all child rows in explicit order (files → tokens → invites
    → project) because the FKs don't carry an ON DELETE CASCADE. Also
    drops the in-memory MPAC session so any live WS clients lose the
    coordinator on their next reconnect; existing connections operate
    against a stale reference until they disconnect, then fail
    membership check (no tokens left) and can't re-join.

    Members who just want to leave the project should call
    ``POST /api/projects/{id}/leave`` instead. Owners cannot "leave" —
    they must delete or transfer ownership (transfer isn't implemented).
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "Only the project owner can delete this project")

    # Cascade in dependency order.
    n_files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id
    ).delete(synchronize_session=False)
    n_tokens = db.query(Token).filter(
        Token.project_id == project_id
    ).delete(synchronize_session=False)
    n_invites = db.query(Invite).filter(
        Invite.project_id == project_id
    ).delete(synchronize_session=False)
    db.delete(project)
    db.commit()

    # Evict in-memory MPAC session AFTER commit so a concurrent request
    # that's about to create state sees the DB already-gone.
    session_registry.drop(project_id)

    log.info(
        "Project deleted: id=%s name=%s owner=%s files=%d tokens=%d invites=%d",
        project_id, project.name, user.id, n_files, n_tokens, n_invites,
    )
    # 204 No Content — FastAPI will skip the response body.
    return None


@router.post("/projects/{project_id}/reset-to-seed", status_code=204)
def reset_project_to_seed(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Owner-only. Overwrite the canonical ``notes_app`` demo files
    in PROJECT_ID back to seed state.

    Project URL, members, invite codes, and any non-canonical files
    the user added are unchanged. Active intents clear naturally on
    next relay reconnect — we don't touch the in-memory session.

    Designed for the unified internal-beta playbook where each test
    pass mutates ``auth.py`` / ``db.py`` etc. and the next pass needs
    a clean slate without re-creating the project (URL + invites
    would all churn).
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "Only the project owner can reset this project")

    n_overwritten = 0
    n_created = 0
    for path, content in NOTES_APP_SEED.items():
        row = db.query(ProjectFile).filter(
            ProjectFile.project_id == project_id,
            ProjectFile.path == path,
        ).first()
        if row:
            row.content = content
            n_overwritten += 1
        else:
            db.add(ProjectFile(project_id=project_id, path=path, content=content))
            n_created += 1
    db.commit()

    log.info(
        "Project reset to seed: id=%s name=%s owner=%s overwritten=%d created=%d",
        project_id, project.name, user.id, n_overwritten, n_created,
    )
    return None


@router.post("/projects/{project_id}/leave", status_code=204)
def leave_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the caller's own membership from a project.

    Membership = any live (non-revoked) Token for (user_id, project_id).
    We revoke ALL of that user's tokens on this project, including the
    agent-relay token — so leaving also kills the Claude relay if it's
    running. Owners can't leave (must delete); returns 403.

    Idempotent: calling leave when you're not a member returns 204
    anyway (no tokens to revoke).
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.owner_id == user.id:
        raise HTTPException(
            403,
            "Owners can't leave their own project — delete it instead "
            "(DELETE /api/projects/{id}).",
        )

    n = db.query(Token).filter(
        Token.user_id == user.id,
        Token.project_id == project_id,
        Token.is_revoked == False,  # noqa: E712
    ).update({Token.is_revoked: True}, synchronize_session=False)
    db.commit()

    log.info(
        "User %s left project %s (revoked %d token(s))",
        user.id, project_id, n,
    )
    return None


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
