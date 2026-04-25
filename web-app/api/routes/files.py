"""Project file CRUD — the persistent backing store for the editor pane.

Paths are POSIX-style strings unique per project. Directories are implicit:
they appear in the tree when at least one file lives underneath them, and
disappear when the last one is deleted. Callers (the frontend) build the
tree view from the flat path list.

Auth model mirrors ``GET /api/projects/{id}``: the caller must hold a live
(non-revoked) Token on the project. Any member can read/write/delete.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

# get_user_or_agent accepts both the user's browser JWT and an MPAC agent
# bearer token. That lets the mpac-mcp-relay's relay_tools subprocess (running
# as a claude -p MCP server) read/write the same files as the user's browser.
# We also pull AuthCtx + assert_token_scope so each route can refuse a leaked
# agent token from project A being replayed against project B (P1.1 fix).
from ..auth import AuthCtx, assert_token_scope, get_user_or_agent
from ..database import get_db
from ..models import Project, ProjectFile, Token, User
from ..mpac_bridge import broadcast_project_event
from ..schemas import (
    ProjectFileContent, ProjectFileListItem, ProjectFileListResponse,
    ProjectFileUpsert,
)
from .files_seed import DEMO_FILES

router = APIRouter()

# Hard caps — we store content inline in SQLite, so large files would bloat
# the DB and slow list responses. 1 MiB per file is generous for hand-edited
# source; we'll revisit if users ask for bigger.
MAX_FILE_BYTES = 1 * 1024 * 1024
MAX_PATH_LEN = 1024


def _assert_member(db: Session, user_id: int, project_id: int) -> Project:
    """Return the project iff the user holds a live token on it."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    membership = db.query(Token).filter(
        Token.user_id == user_id,
        Token.project_id == project_id,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if not membership:
        raise HTTPException(403, "You are not a member of this project")
    return project


def _assert_caller_holds_intent(
    project_id: int,
    user_id: int,
    path: str,
    token_project_id: int | None,
) -> None:
    """Refuse the write if the caller has no active intent covering ``path``.

    This is the gate that closes the autosave-bypass hole — without it, a
    human typing in the editor (or any HTTP client with a valid token) can
    silently overwrite an agent's in-flight work, defeating MPAC's central
    promise. Frontends MUST call ``begin_task`` over WS (or the relay MUST
    call POST /api/agent/intents) before hitting this PUT/DELETE.

    The caller's MPAC principal_id is one of:
      * ``user:{user_id}`` for browser editors (JWT auth, ``token_project_id``
        is None)
      * ``agent:user-{user_id}`` for the local Claude relay (agent token)

    Greenfield carve-out: if no live coordinator session exists for the
    project, we let the write through. This covers brand-new projects
    where nobody has ever connected a WS — there's no one to coordinate
    with. The first WS HELLO turns the gate on.
    """
    # Local import to avoid pulling the bridge into module-load order.
    from ..mpac_bridge import registry as session_registry

    session = session_registry.get(project_id)
    if session is None:
        return  # No live coordinator → no peers to protect → allow.

    is_agent = token_project_id is not None
    expected_principal = (
        f"agent:user-{user_id}" if is_agent else f"user:{user_id}"
    )

    for intent in session.coordinator.intents.values():
        if intent.principal_id != expected_principal:
            continue
        # Skip terminated intents — coordinator keeps them around for audit
        # but they don't carry edit rights.
        state_name = getattr(intent.state_machine, "state", None)
        if state_name in ("Withdrawn", "Completed", "Terminated", "Superseded"):
            continue
        scope = getattr(intent, "scope", None)
        resources = list(getattr(scope, "resources", []) or []) if scope else []
        if path in resources:
            return  # Found a covering intent — write is coordinated.

    raise HTTPException(
        409,
        f"INTENT_REQUIRED: caller has no active intent covering {path!r}. "
        "Call begin_task (browser) or POST /api/agent/intents (relay) first.",
    )


def _normalize_path(raw: str) -> str:
    """Reject traversal + normalize leading slashes so paths are canonical."""
    if not raw or not raw.strip():
        raise HTTPException(400, "Path cannot be empty")
    path = raw.strip().lstrip("/")
    if len(path) > MAX_PATH_LEN:
        raise HTTPException(400, f"Path exceeds {MAX_PATH_LEN} characters")
    # Defence in depth: project files live in a virtual FS (DB rows, not
    # disk), but .. would still let a client confuse the tree builder and
    # is never legitimate. Same for embedded backslashes on POSIX.
    if ".." in path.split("/") or "\\" in path:
        raise HTTPException(400, "Invalid path")
    return path


def _seed_demo_if_empty(db: Session, project_id: int) -> None:
    """Insert the demo file set on first access so new projects aren't blank.

    Idempotent by construction — only runs when the project has zero files.
    Callers should invoke this before reading or listing.
    """
    exists = db.query(ProjectFile.id).filter(
        ProjectFile.project_id == project_id
    ).first()
    if exists:
        return
    for path, content in DEMO_FILES:
        db.add(ProjectFile(project_id=project_id, path=path, content=content))
    db.commit()


@router.get("/projects/{project_id}/files", response_model=ProjectFileListResponse)
def list_files(
    project_id: int,
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    assert_token_scope(ctx, project_id)
    user = ctx.user
    _assert_member(db, user.id, project_id)
    _seed_demo_if_empty(db, project_id)
    rows = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id
    ).order_by(ProjectFile.path).all()
    return ProjectFileListResponse(files=[
        ProjectFileListItem(path=r.path, updated_at=r.updated_at.isoformat())
        for r in rows
    ])


@router.get(
    "/projects/{project_id}/files/content",
    response_model=ProjectFileContent,
)
def read_file(
    project_id: int,
    path: str = Query(..., description="POSIX path, e.g. src/api.py"),
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    assert_token_scope(ctx, project_id)
    user = ctx.user
    _assert_member(db, user.id, project_id)
    norm = _normalize_path(path)
    row = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.path == norm,
    ).first()
    if not row:
        raise HTTPException(404, "File not found")
    return ProjectFileContent(
        path=row.path,
        content=row.content,
        updated_at=row.updated_at.isoformat(),
    )


@router.put(
    "/projects/{project_id}/files/content",
    response_model=ProjectFileContent,
)
def upsert_file(
    project_id: int,
    req: ProjectFileUpsert,
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    """Create if missing, otherwise overwrite. Editor autosave hits this.

    Coordination invariant (enforced below): the caller MUST hold an active
    (non-withdrawn) intent whose scope includes ``req.path``. This is what
    stops a human typing in the editor from silently overwriting an agent's
    in-flight work — the browser editor announces an intent before it lets
    the user edit, and the relay's submit_change tool announces before
    committing. If you hit ``409 INTENT_REQUIRED`` here, that means the
    caller forgot to announce first.

    Greenfield carve-out: if no live MPAC session exists for the project
    yet (no participants ever connected), we allow the write — there's no
    one to coordinate with. Once any participant has joined, the gate
    becomes active.
    """
    assert_token_scope(ctx, project_id)
    user = ctx.user
    _assert_member(db, user.id, project_id)
    norm = _normalize_path(req.path)
    _assert_caller_holds_intent(project_id, user.id, norm, ctx.token_project_id)
    if len(req.content.encode("utf-8", errors="ignore")) > MAX_FILE_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_FILE_BYTES} bytes")
    row = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.path == norm,
    ).first()
    if row:
        row.content = req.content
    else:
        row = ProjectFile(project_id=project_id, path=norm, content=req.content)
        db.add(row)
    db.commit()
    db.refresh(row)
    broadcast_project_event(
        project_id,
        "file_changed",
        {"path": norm, "updated_at": row.updated_at.isoformat()},
        exclude_principal=f"user:{user.id}",
    )
    return ProjectFileContent(
        path=row.path,
        content=row.content,
        updated_at=row.updated_at.isoformat(),
    )


@router.delete("/projects/{project_id}/files")
def delete_file(
    project_id: int,
    path: str = Query(..., description="POSIX path, e.g. src/api.py"),
    ctx: AuthCtx = Depends(get_user_or_agent),
    db: Session = Depends(get_db),
):
    assert_token_scope(ctx, project_id)
    user = ctx.user
    _assert_member(db, user.id, project_id)
    norm = _normalize_path(path)
    _assert_caller_holds_intent(project_id, user.id, norm, ctx.token_project_id)
    row = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.path == norm,
    ).first()
    if not row:
        raise HTTPException(404, "File not found")
    db.delete(row)
    db.commit()
    broadcast_project_event(
        project_id, "file_deleted", {"path": norm}, exclude_principal=f"user:{user.id}",
    )
    return {"status": "deleted", "path": norm}
