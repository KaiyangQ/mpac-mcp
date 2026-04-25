"""User registration + login routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SignupCode, User
from ..schemas import RegisterRequest, LoginRequest, AuthResponse, MeResponse
from ..auth import hash_password, verify_password, create_jwt, get_current_user

router = APIRouter()


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
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
    return AuthResponse(
        token=create_jwt(user.id, user.email),
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return AuthResponse(
        token=create_jwt(user.id, user.email),
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    """Bootstrap: verify a stored JWT and return current user info."""
    return MeResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )
