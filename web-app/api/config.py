"""App-wide configuration loaded from environment variables + repo-local
``local_config.json`` (gitignored, stores the developer's Anthropic API key
for local dev only — production uses per-user BYOK keys stored in the DB)."""
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

# Environment marker — "production" enables fail-closed defaults.
ENV = os.environ.get("MPAC_WEB_ENV", "development").lower()
IS_PRODUCTION = ENV == "production"

# Database
DB_DIR = Path(os.environ.get("MPAC_WEB_DB_DIR", Path(__file__).resolve().parent))
DB_PATH = DB_DIR / "mpac_web.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# JWT — refuse the dev default in production so we never accidentally ship
# a predictable signing secret. In dev we keep a stable default so tests /
# local runs don't have to juggle env vars.
_JWT_DEFAULT = "dev-secret-change-in-prod"
JWT_SECRET = os.environ.get("MPAC_WEB_JWT_SECRET", _JWT_DEFAULT)
if IS_PRODUCTION and JWT_SECRET == _JWT_DEFAULT:
    raise RuntimeError(
        "MPAC_WEB_JWT_SECRET must be set to a strong secret in production "
        "(MPAC_WEB_ENV=production). Generate one with `python -c \"import "
        "secrets; print(secrets.token_urlsafe(48))\"` and `fly secrets set`."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72

# Fernet encryption key for per-user BYOK Anthropic keys. Must be a
# urlsafe-base64-encoded 32-byte key (Fernet.generate_key()). If absent we
# hard-fail in production so BYOK doesn't silently write plaintext.
ENCRYPTION_KEY = os.environ.get("MPAC_WEB_ENCRYPTION_KEY", "")
if IS_PRODUCTION and not ENCRYPTION_KEY:
    raise RuntimeError(
        "MPAC_WEB_ENCRYPTION_KEY must be set in production. Generate one with "
        "`python -c \"from cryptography.fernet import Fernet; "
        "print(Fernet.generate_key().decode())\"` and `fly secrets set`."
    )

# Signup gate — comma-separated list of invite codes accepted by /api/register.
# Each code is single-use; we seed a SignupCode table on startup from this
# list (existing rows are left alone so deploys don't resurrect used codes).
INVITE_CODES = [
    c.strip() for c in os.environ.get("MPAC_WEB_INVITE_CODES", "").split(",")
    if c.strip()
]

# CORS — prod reads CSV env; dev always allows any localhost port.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("MPAC_WEB_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# MPAC Coordinator
COORDINATOR_URL = os.environ.get(
    "MPAC_COORDINATOR_URL", "wss://mpac-demo.fly.dev"
)

# Claude API — legacy platform-level fallback, used ONLY in dev if a user
# hasn't set their own BYOK key yet. In production, every user must bring
# their own key via /api/settings/anthropic-key. `chat` is the only caller.
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
