"""App-wide configuration loaded from environment variables + repo-local
``local_config.json`` (gitignored, stores the user's Anthropic API key)."""
from __future__ import annotations
import json
import os
from pathlib import Path


def _load_local_config() -> dict:
    """Best-effort read of ``<repo>/local_config.json`` — optional."""
    # walk up from this file until we find the repo root (which has this file)
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        cfg = parent / "local_config.json"
        if cfg.is_file():
            try:
                return json.loads(cfg.read_text())
            except (OSError, json.JSONDecodeError):
                break
    return {}


_LOCAL = _load_local_config()
_ANTHROPIC_CFG = _LOCAL.get("anthropic", {}) if isinstance(_LOCAL, dict) else {}

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

# Claude API — accept either a regular API key OR a Bearer OAuth token.
# Priority: env var > local_config.json (<repo>/local_config.json).
# Claude Code stores an OAuth token in the macOS keychain with `user:inference`
# scope; when exported as ANTHROPIC_AUTH_TOKEN we can re-use it instead of
# asking the user for a separate api_key.
ANTHROPIC_API_KEY = (
    os.environ.get("ANTHROPIC_API_KEY")
    or _ANTHROPIC_CFG.get("api_key")
    or ""
)
ANTHROPIC_AUTH_TOKEN = (
    os.environ.get("ANTHROPIC_AUTH_TOKEN")
    or _ANTHROPIC_CFG.get("auth_token")
    or ""
)
CLAUDE_MODEL = (
    os.environ.get("MPAC_CLAUDE_MODEL")
    or _ANTHROPIC_CFG.get("model")
    or "claude-sonnet-4-6"
)
