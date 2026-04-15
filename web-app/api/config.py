"""App-wide configuration loaded from environment variables."""
from __future__ import annotations
import os
from pathlib import Path

# Database
DB_DIR = Path(os.environ.get("MPAC_WEB_DB_DIR", Path(__file__).resolve().parent))
DB_PATH = DB_DIR / "mpac_web.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# JWT
JWT_SECRET = os.environ.get("MPAC_WEB_JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72

# MPAC Coordinator
COORDINATOR_URL = os.environ.get(
    "MPAC_COORDINATOR_URL", "wss://mpac-demo.fly.dev"
)

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("MPAC_CLAUDE_MODEL", "claude-sonnet-4-20250514")
