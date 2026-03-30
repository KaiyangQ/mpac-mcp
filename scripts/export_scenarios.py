"""Export executable MPAC scenarios for the static frontend."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mpac.scenarios import run_all_scenarios


def main() -> None:
    target = ROOT / "frontend" / "scenarios-data.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(run_all_scenarios(), indent=2)
    target.write_text(f"window.MPAC_SCENARIOS = {payload};\n", encoding="utf-8")


if __name__ == "__main__":
    main()
