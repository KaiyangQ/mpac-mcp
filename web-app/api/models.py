"""SQLAlchemy ORM models for the MPAC Web App."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
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
    """Per-user per-project MPAC bearer token (Plan C credential)."""
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_value = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    roles = Column(Text, default='["contributor"]')  # JSON array
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_revoked = Column(Boolean, default=False)

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
