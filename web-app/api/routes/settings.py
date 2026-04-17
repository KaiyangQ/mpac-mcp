"""User settings — BYOK Anthropic API key management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..crypto import decrypt_str, encrypt_str
from ..database import get_db
from ..models import User
from ..schemas import AnthropicKeyStatus, AnthropicKeyUpdate

router = APIRouter()


def _mask_key(key: str) -> str:
    """Return e.g. ``sk-ant-...xyz1`` so the frontend can confirm which key
    is on file without ever echoing the full secret. 4 tail chars is enough
    to distinguish the handful of keys any one user rotates between."""
    if not key:
        return ""
    if len(key) <= 12:
        return key[:3] + "…"
    return f"{key[:7]}…{key[-4:]}"


@router.get("/settings/anthropic-key", response_model=AnthropicKeyStatus)
def get_anthropic_key_status(user: User = Depends(get_current_user)):
    """Tell the frontend whether this user has a key on file + a masked preview."""
    if not user.anthropic_api_key_encrypted:
        return AnthropicKeyStatus(has_key=False)
    plain = decrypt_str(user.anthropic_api_key_encrypted)
    if plain is None:
        # DB row exists but we can't decrypt it — likely the server's
        # ENCRYPTION_KEY was rotated. Treat as no key; frontend will ask
        # the user to re-enter. We don't clear the row here — let the user
        # explicitly DELETE so we don't lose history to a config mistake.
        return AnthropicKeyStatus(has_key=False)
    return AnthropicKeyStatus(has_key=True, key_preview=_mask_key(plain))


@router.put("/settings/anthropic-key", response_model=AnthropicKeyStatus)
def set_anthropic_key(
    req: AnthropicKeyUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store an encrypted Anthropic API key for this user. Overwrites any
    previous key. Minimal validation — we just check the Anthropic prefix
    so obvious typos (pasting the wrong secret) get caught early."""
    key = (req.api_key or "").strip()
    if not key:
        raise HTTPException(400, "API key cannot be empty")
    if not (key.startswith("sk-ant-") or key.startswith("sk-")):
        raise HTTPException(
            400,
            "This doesn't look like an Anthropic API key "
            "(should start with 'sk-ant-…'). Copy it from console.anthropic.com.",
        )
    user.anthropic_api_key_encrypted = encrypt_str(key)
    db.commit()
    return AnthropicKeyStatus(has_key=True, key_preview=_mask_key(key))


@router.delete("/settings/anthropic-key", response_model=AnthropicKeyStatus)
def delete_anthropic_key(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.anthropic_api_key_encrypted = None
    db.commit()
    return AnthropicKeyStatus(has_key=False)
