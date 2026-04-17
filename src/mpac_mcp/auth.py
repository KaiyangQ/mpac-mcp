"""Credential verifiers for mpac-mcp sidecar deployments.

Provides the default ``build_env_verifier()`` that reads a JSON mapping from
an environment variable and turns it into an ``mpac`` ``CredentialVerifier``
callable suitable for passing into ``MPACServer(credential_verifier=...)``.

Intended for small-to-medium deployments where the token table fits in an
env var (say, up to ~50 tokens). Larger deployments should wire their own
verifier against a database or a dedicated auth service.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, Optional

from ._compat import ensure_local_mpac_import

ensure_local_mpac_import()

from mpac_protocol.core.coordinator import CredentialVerifier, VerifyResult


log = logging.getLogger("mpac_mcp.auth")


DEFAULT_ENV_VAR = "MPAC_TOKEN_TABLE"


def build_env_verifier(
    env_var: str = DEFAULT_ENV_VAR,
    *,
    strict: bool = True,
) -> Optional[CredentialVerifier]:
    """Build a ``CredentialVerifier`` from a JSON-encoded env var.

    Expected format of the env var::

        {
            "<token-string>": {
                "allowed_sessions": ["proj-alpha", "proj-beta"],
                "roles": ["contributor"]
            },
            ...
        }

    Each key is a bearer token value. Each value carries the list of session
    ids that token is authorized to join and (optionally) the roles it grants.

    If ``allowed_sessions`` contains the single wildcard string ``"*"``, the
    token can join any session — useful for an operator/debug token.

    Returns ``None`` when the env var is unset or empty (callers should treat
    this as "no verifier configured" and fall back to Open profile).

    Raises ``ValueError`` on malformed JSON or wrong shape when ``strict=True``
    (the default). ``strict=False`` swallows errors and returns ``None``,
    useful when you want a best-effort load with clear logs instead of a hard
    failure at startup.
    """
    raw = os.environ.get(env_var)
    if not raw:
        log.info(f"{env_var} not set; build_env_verifier returning None (Open profile)")
        return None

    try:
        table = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"{env_var} is not valid JSON: {exc}"
        if strict:
            raise ValueError(msg) from exc
        log.warning(msg)
        return None

    if not isinstance(table, dict):
        msg = f"{env_var} must decode to a JSON object (got {type(table).__name__})"
        if strict:
            raise ValueError(msg)
        log.warning(msg)
        return None

    # Light-touch validation of entries. We don't want to crash at request
    # time just because one entry is malformed — we want to fail at startup.
    validated: Dict[str, Dict[str, Any]] = {}
    for token, entry in table.items():
        if not isinstance(token, str) or not token:
            if strict:
                raise ValueError(f"{env_var}: token keys must be non-empty strings")
            continue
        if not isinstance(entry, dict):
            if strict:
                raise ValueError(f"{env_var}: entry for token must be an object")
            continue
        allowed = entry.get("allowed_sessions", [])
        if not isinstance(allowed, list) or not all(isinstance(s, str) for s in allowed):
            if strict:
                raise ValueError(
                    f"{env_var}: allowed_sessions must be a list of strings"
                )
            continue
        roles = entry.get("roles")
        if roles is not None and (
            not isinstance(roles, list) or not all(isinstance(r, str) for r in roles)
        ):
            if strict:
                raise ValueError(f"{env_var}: roles must be a list of strings or omitted")
            continue
        validated[token] = {"allowed_sessions": allowed, "roles": roles}

    log.info(f"{env_var}: loaded {len(validated)} token(s)")

    def verify(credential: Dict[str, Any], session_id: str) -> VerifyResult:
        cred_type = credential.get("type")
        if cred_type != "bearer_token":
            return VerifyResult.reject(
                f"unsupported credential type {cred_type!r}; "
                "this verifier only accepts 'bearer_token'"
            )
        cred_value = credential.get("value")
        if not isinstance(cred_value, str) or not cred_value:
            return VerifyResult.reject("missing or empty bearer token value")

        entry = validated.get(cred_value)
        if entry is None:
            return VerifyResult.reject("unknown bearer token")

        allowed = entry["allowed_sessions"]
        if "*" not in allowed and session_id not in allowed:
            return VerifyResult.reject(
                f"bearer token not authorized for session {session_id!r}"
            )

        return VerifyResult.accept(granted_roles=entry["roles"])

    return verify


def build_static_verifier(
    token_table: Dict[str, Dict[str, Any]],
) -> CredentialVerifier:
    """Build a verifier from an in-memory token table (for tests / embedding).

    Same entry shape as ``build_env_verifier`` but takes a dict directly
    instead of reading from the environment. Always returns a verifier
    (no None fallback).
    """

    def verify(credential: Dict[str, Any], session_id: str) -> VerifyResult:
        cred_type = credential.get("type")
        if cred_type != "bearer_token":
            return VerifyResult.reject(
                f"unsupported credential type {cred_type!r}"
            )
        cred_value = credential.get("value")
        if not isinstance(cred_value, str) or not cred_value:
            return VerifyResult.reject("missing or empty bearer token value")
        entry = token_table.get(cred_value)
        if entry is None:
            return VerifyResult.reject("unknown bearer token")
        allowed = entry.get("allowed_sessions", [])
        if "*" not in allowed and session_id not in allowed:
            return VerifyResult.reject(
                f"bearer token not authorized for session {session_id!r}"
            )
        return VerifyResult.accept(granted_roles=entry.get("roles"))

    return verify
