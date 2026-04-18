"""Seed the 4 dogfood test accounts (Alice/Bob/Carol/Dave) into the local
SQLite DB — mirrors what's already in AWS Lightsail per BETA_ACCESS.md.

Idempotent: skips any account whose email is already present. Run from
repo root:

    PYTHONPATH=web-app .venv/bin/python scripts/seed_test_users.py
"""
from __future__ import annotations

from api.auth import hash_password
from api.database import SessionLocal, init_db
from api.models import User

ACCOUNTS = [
    ("Alice", "alice@mpac.test"),
    ("Bob",   "bob@mpac.test"),
    ("Carol", "carol@mpac.test"),
    ("Dave",  "dave@mpac.test"),
]
PASSWORD = "mpac-test-2026"


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        existing = {u.email for u in db.query(User).all()}
        inserted = 0
        for display, email in ACCOUNTS:
            if email in existing:
                print(f"skip (exists): {email}")
                continue
            db.add(User(
                email=email,
                password_hash=hash_password(PASSWORD),
                display_name=display,
            ))
            inserted += 1
            print(f"added:         {email}  ({display})")
        if inserted:
            db.commit()
        print(f"\nTotal inserted: {inserted}. Password for all: {PASSWORD!r}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
