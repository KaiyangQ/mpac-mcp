"""SQLAlchemy ORM models for the MPAC Web App."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(128), nullable=False)
    # Per-user Anthropic API key, encrypted with Fernet (see api/crypto.py).
    # NULL = user hasn't brought their own key yet ⇒ /api/chat will 402.
    anthropic_api_key_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    owned_projects = relationship("Project", back_populates="owner")
    tokens = relationship("Token", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    owner = relationship("User", back_populates="owned_projects")
    tokens = relationship("Token", back_populates="project")
    invites = relationship("Invite", back_populates="project")


class Token(Base):
    """Per-user per-project MPAC bearer token (Plan C credential).

    A given (user_id, project_id) pair can have multiple tokens when
    is_agent differs: one for the user's browser session, another for
    their local Claude Code relay. Membership is granted by any live
    (non-revoked) token regardless of is_agent.
    """
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_value = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    roles = Column(Text, default='["contributor"]')  # JSON array
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False)
    # True when minted for an mpac-mcp relay (local Claude Code bridge).
    # The /ws/relay endpoint only accepts is_agent=True tokens; the human
    # browser path (/ws/session) checks membership via any live token but
    # treats is_agent=False as the user's own credential.
    is_agent = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="tokens")
    project = relationship("Project", back_populates="tokens")


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invite_code = Column(String(64), unique=True, nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    roles = Column(Text, default='["contributor"]')  # JSON array
    used_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="invites")
    created_by = relationship("User", foreign_keys=[created_by_id])
    used_by = relationship("User", foreign_keys=[used_by_id])


class ProjectFile(Base):
    """A file inside a project's virtual filesystem.

    ``path`` is a POSIX-style forward-slashed path, unique per project.
    Directories aren't stored as rows — they're derived on read from the
    set of existing file paths. Deleting a file therefore implicitly
    collapses any directory that becomes empty.
    """
    __tablename__ = "project_files"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_project_files_path"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    path = Column(String(1024), nullable=False)
    content = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class SignupCode(Base):
    """Single-use invite codes that gate /api/register for the semi-public beta.

    Seeded at startup from ``MPAC_WEB_INVITE_CODES`` — we only insert rows that
    don't already exist, so a code that's been marked used never gets resurrected
    by a deploy that still has it in the env var.
    """
    __tablename__ = "signup_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    used_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    used_by = relationship("User", foreign_keys=[used_by_id])
