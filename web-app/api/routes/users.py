"""User registration + login routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import IS_PRODUCTION, JWT_EXPIRE_HOURS
from ..database import get_db
from ..models import SignupCode, User
from ..schemas import RegisterRequest, LoginRequest, AuthResponse, MeResponse
from ..auth import hash_password, verify_password, create_jwt, get_current_user

router = APIRouter()


# Cookie name + flags shared between /register, /login, /logout, and the
# WS handler (main.py reads this cookie on upgrade). Gate ``Secure`` on
# prod because dev runs over plain HTTP and Secure cookies wouldn't even
# round-trip; ``SameSite=Lax`` keeps the cookie out of cross-site
# requests other than top-level navigation, which is the right default
# for an auth cookie + we additionally check Origin on the WS upgrade
# in ``main._origin_allowed`` so cross-site WS attempts are refused
# regardless of cookie behaviour.
_COOKIE_NAME = "mpac_jwt"
_COOKIE_MAX_AGE = JWT_EXPIRE_HOURS * 3600


def _set_jwt_cookie(response: Response, jwt_value: str) -> None:
    """Mirror the just-issued JWT into an HttpOnly cookie. The browser
    sends it automatically on the WS upgrade, so we no longer have to put
    the token in ``?token=`` (which would land in proxy / browser-history
    / diagnostic logs). The same JWT is ALSO returned in the JSON body
    for now — ``api.ts`` keeps it in localStorage so the existing
    Authorization-header path for ``/api/*`` HTTP routes keeps working
    without further client changes; that mirror can go once we move HTTP
    auth to cookies in a follow-up.
    """
    response.set_cookie(
        key=_COOKIE_NAME,
        value=jwt_value,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=AuthResponse)
def register(
    req: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    # 1. Invite-code gate (semi-public beta). Codes are single-use — the row
    # is seeded at startup from MPAC_WEB_INVITE_CODES and marked used here.
    code = (req.invite_code or "").strip()
    if not code:
        raise HTTPException(400, "Invite code is required for this beta")

    # 2. Duplicate email guard. We do this BEFORE the atomic code-burn so
    # we don't waste a single-use signup code on a duplicate registration.
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")

    # 3. Insert the user, then atomically claim the signup code in a single
    # UPDATE — ``used_by_id IS NULL`` in the WHERE clause is the race-safe
    # check-and-set that the previous read-then-write code lacked. Two
    # concurrent registrations on the same code now have exactly one winner;
    # the loser's UPDATE matches zero rows, we roll back the user insert,
    # and the second caller gets a clean 403.
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    db.flush()  # populate user.id before we reference it in the UPDATE
    now = datetime.now(timezone.utc)
    result = db.execute(
        update(SignupCode)
        .where(SignupCode.code == code, SignupCode.used_by_id.is_(None))
        .values(used_by_id=user.id, used_at=now)
    )
    if result.rowcount == 0:
        # Claim lost — disambiguate "no such code" vs "already used" so the
        # error message is actionable, then roll back the user insert.
        db.rollback()
        existing = db.query(SignupCode).filter(SignupCode.code == code).first()
        if existing is None:
            raise HTTPException(403, "Invalid invite code")
        raise HTTPException(403, "Invite code has already been used")
    db.commit()
    db.refresh(user)
    jwt_token = create_jwt(user.id, user.email)
    _set_jwt_cookie(response, jwt_token)
    return AuthResponse(
        token=jwt_token,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    jwt_token = create_jwt(user.id, user.email)
    _set_jwt_cookie(response, jwt_token)
    return AuthResponse(
        token=jwt_token,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/logout", status_code=204)
def logout(response: Response):
    """Clear the WS-auth cookie. Frontend ``logout()`` already wipes the
    JWT from localStorage; this endpoint exists so the cookie side stays
    in sync — without it a browser that "logged out" would keep sending
    the cookie on subsequent WS upgrades until it expired naturally
    (72h). Idempotent: safe to call when no cookie is set.
    """
    response.delete_cookie(_COOKIE_NAME, path="/")
    return None


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    """Bootstrap: verify a stored JWT and return current user info."""
    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )
