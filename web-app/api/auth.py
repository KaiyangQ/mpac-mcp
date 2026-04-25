"""JWT + password hashing utilities + FastAPI auth dependency."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS
from .database import get_db
from .models import User


@dataclass
class AuthCtx:
    """Resolved authenticated principal + the project scope, if the credential
    is a project-scoped agent token. ``token_project_id`` is ``None`` when the
    caller authenticated with a (user-wide) JWT.

    Routes that need to scope their effect to a specific project should call
    :func:`assert_token_scope` to refuse any cross-project use of an agent
    token. JWT-authenticated requests aren't restricted by this — JWT auth is
    user-scoped, not project-scoped, so cross-project access is the intended
    semantic.
    """
    user: User
    token_project_id: Optional[int] = None


def assert_token_scope(ctx: "AuthCtx", project_id: int) -> None:
    """Refuse the request if ``ctx`` was authenticated with an agent token
    whose project_id does not match the requested project.

    JWT-authenticated requests (``ctx.token_project_id is None``) pass through
    — JWT is user-scoped, the caller's membership is verified separately.
    """
    if ctx.token_project_id is not None and ctx.token_project_id != project_id:
        raise HTTPException(
            403,
            "Agent token is scoped to a different project; cross-project use "
            "is not allowed",
        )


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
) -> AuthCtx:
    """Like :func:`get_current_user`, but also accepts an MPAC agent bearer token.

    The bearer can be either:
      * A JWT — the user's browser session credential (same as get_current_user).
        Returned ``AuthCtx`` has ``token_project_id=None``.
      * An agent ``Token.token_value`` — minted via
        ``POST /api/projects/{id}/agent-token``, carried by mpac-mcp-relay and
        its relay_tools MCP subprocess. Returned ``AuthCtx`` carries the
        ``project_id`` the token was minted for, so downstream code can refuse
        cross-project use via :func:`assert_token_scope`.

    Revoked agent tokens are rejected. Note: this function does NOT verify
    that the token's ``project_id`` matches the requested project — the route
    must call :func:`assert_token_scope` (or otherwise bind the token to the
    specific resource being accessed) to prevent a leaked agent token from
    project A from being replayed against project B.
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
        return AuthCtx(user=user, token_project_id=None)

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
    return AuthCtx(user=user, token_project_id=tok.project_id)
