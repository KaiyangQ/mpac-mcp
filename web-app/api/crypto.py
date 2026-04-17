"""Fernet symmetric encryption for per-user Anthropic API keys (BYOK).

We never store plaintext keys in the DB — the column is encrypted at rest
with the Fernet key from ``MPAC_WEB_ENCRYPTION_KEY``. Encryption is only
used for the API key column, not JWTs (those are HMAC-signed, not encrypted).

In development the env var may be unset; we fall back to a well-known dev
key so local sessions survive a restart. ``config.py`` refuses to boot
production with an empty ENCRYPTION_KEY, so the dev fallback can only fire
when MPAC_WEB_ENV != production.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from .config import ENCRYPTION_KEY, IS_PRODUCTION


# Well-known 32-byte urlsafe-base64 key. DEV-ONLY — any data encrypted with
# this is trivially readable. config.py's fail-closed check means this never
# runs in production.
_DEV_KEY = b"kZ3Yqx2NnPeWmB7hVcF8tA1RsL4gJ6dE0oU5iT9yX_0="


def _cipher() -> Fernet:
    key = ENCRYPTION_KEY.encode() if ENCRYPTION_KEY else _DEV_KEY
    return Fernet(key)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning a urlsafe-base64 token."""
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt_str(ciphertext: str) -> str | None:
    """Decrypt a Fernet token. Returns ``None`` if invalid or corrupted."""
    if not ciphertext:
        return None
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError):
        return None


__all__ = ["encrypt_str", "decrypt_str", "IS_PRODUCTION"]
