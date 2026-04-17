"""User registration + login routes."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
    row = db.query(SignupCode).filter(SignupCode.code == code).first()
    if not row:
        raise HTTPException(403, "Invalid invite code")
    if row.used_by_id is not None:
        raise HTTPException(403, "Invite code has already been used")

    # 2. Duplicate email guard.
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(400, "Email already registered")

    # 3. Create user + burn the code atomically.
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    db.flush()  # populate user.id before we reference it on the code row
    row.used_by_id = user.id
    row.used_at = datetime.now(timezone.utc)
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
