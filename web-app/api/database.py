"""SQLAlchemy engine + session factory."""
from __future__ import annotations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yield a DB session, auto-close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _lightweight_migrations() -> None:
    """Hand-rolled ALTER TABLEs for the columns create_all() can't add.

    SQLAlchemy's ``Base.metadata.create_all`` only creates missing tables; it
    doesn't touch columns on tables that already exist. The semi-public beta
    added ``users.anthropic_api_key_encrypted`` to a table that may already
    have rows in production / local dev, so we ALTER it in if absent.

    Keep this short and idempotent — for anything heavier we should switch
    to Alembic.
    """
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("users")}
        if "anthropic_api_key_encrypted" not in cols:
            with engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE users ADD COLUMN "
                    "anthropic_api_key_encrypted TEXT"
                ))


def init_db():
    """Create all tables (idempotent) + run lightweight ALTER migrations."""
    Base.metadata.create_all(bind=engine)
    _lightweight_migrations()
