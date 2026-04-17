"""Compatibility helpers for local development."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def ensure_local_mpac_import() -> None:
    """Add the local mpac package source tree to sys.path when needed."""
    if importlib.util.find_spec("mpac_protocol") is not None:
        return

    repo_root = Path(__file__).resolve().parents[3]
    local_src = repo_root / "mpac-package" / "src"
    if local_src.exists():
        sys.path.insert(0, str(local_src))

