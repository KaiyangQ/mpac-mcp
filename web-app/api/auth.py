"""JWT + password hashing utilities + FastAPI auth dependency."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from .database import get_db
from .models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_jwt(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    """Decode and verify a JWT. Returns the payload dict or None if invalid."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract user from `Authorization: Bearer <jwt>` header.

    Raises HTTPException(401) if the header is missing, malformed, expired,
    or references a non-existent user.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    payload = decode_jwt(authorization[7:])
    if not payload:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def get_user_or_agent(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Like get_current_user, but also accepts an MPAC agent bearer token.

    The bearer can be either:
      * A JWT — the user's browser session credential (same as get_current_user)
      * An agent Token.token_value — minted via POST /api/projects/{id}/agent-token,
        carried by mpac-mcp-relay and its relay_tools MCP subprocess.

    In both cases we return the ``User`` the token belongs to, so downstream
    handlers see a consistent "who is this request on behalf of" answer.
    Agent tokens scoped to a specific project still return the user — the
    handler is expected to cross-check project membership itself (e.g. files.py
    already does this via _assert_member). Revoked agent tokens are rejected.
    """
    from .models import Token  # local import avoids circular dep

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    raw = authorization[7:]

    # First try JWT — if it parses, we're done.
    payload = decode_jwt(raw)
    if payload:
        user = db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(401, "User not found")
        return user

    # Otherwise treat the raw string as an MPAC bearer token.
    tok = db.query(Token).filter(
        Token.token_value == raw,
        Token.is_revoked == False,  # noqa: E712
    ).first()
    if tok is None:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, tok.user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user
