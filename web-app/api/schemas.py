"""Pydantic request/response schemas."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Auth ──

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str
    display_name: str


# ── Projects ──

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: int
    session_id: str
    name: str
    owner_id: int
    created_at: str

class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


# ── Tokens ──

class TokenResponse(BaseModel):
    token_value: str
    session_id: str
    roles: list[str]


# ── Invites ──

class InviteCreate(BaseModel):
    roles: list[str] = ["contributor"]

class InviteResponse(BaseModel):
    invite_code: str
    project_name: str
    session_id: str

class InviteAccept(BaseModel):
    invite_code: str


# ── Chat ──

class ChatMessage(BaseModel):
    message: str
    project_id: int
    file_context: Optional[str] = None  # current file content for AI context
    file_path: Optional[str] = None     # current file path
