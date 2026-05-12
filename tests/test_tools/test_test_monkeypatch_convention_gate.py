from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_test_monkeypatch_convention_gate_cli_passes_strict() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "test-monkeypatch-convention", "--strict"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
