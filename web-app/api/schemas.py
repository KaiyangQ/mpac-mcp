"""Pydantic request/response schemas."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Auth ──

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str
    invite_code: str  # Semi-public beta: must match an unused SignupCode row.

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user_id: int
    email: str
    display_name: str

class MeResponse(BaseModel):
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

class InvitePreview(BaseModel):
    """Read-only lookup so /invite/[code] can show project info before accept."""
    invite_code: str
    project_name: str
    session_id: str
    invited_by: str
    used: bool

class InviteAccept(BaseModel):
    invite_code: str


# ── Settings (BYOK Anthropic key) ──

class AnthropicKeyStatus(BaseModel):
    """Never returns the key itself — just whether one is on file."""
    has_key: bool
    key_preview: Optional[str] = None  # e.g. "sk-ant-...1234" for confirmation

class AnthropicKeyUpdate(BaseModel):
    api_key: str


# ── Project files ──

class ProjectFileListItem(BaseModel):
    path: str
    updated_at: str

class ProjectFileListResponse(BaseModel):
    files: list[ProjectFileListItem]

class ProjectFileContent(BaseModel):
    path: str
    content: str
    updated_at: str

class ProjectFileUpsert(BaseModel):
    path: str
    content: str = ""


# ── Chat ──

class ChatMessage(BaseModel):
    message: str
    project_id: int
    file_context: Optional[str] = None  # current file content for AI context
    file_path: Optional[str] = None     # current file path

class ChatReply(BaseModel):
    reply: str
