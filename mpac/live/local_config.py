"""Local config loader for demo secrets and defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "local_config.json"
CONFIG_EXAMPLE_PATH = ROOT / "local_config.example.json"


def load_local_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
