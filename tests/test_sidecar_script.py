import subprocess
import sys
from pathlib import Path


def test_sidecar_script_imports_when_executed_directly():
    script = Path(__file__).resolve().parents[1] / "src" / "mpac_mcp" / "sidecar.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0
    assert "Run a local MPAC sidecar" in result.stdout
