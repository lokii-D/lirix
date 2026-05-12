from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_branch_protection_drift_gate_cli_passes_without_token() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "branch-protection-drift"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(root / "tools"),
            "HOME": os.environ.get("HOME", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout.strip() or "{}")
    assert payload.get("ok") is True
    assert isinstance(payload.get("required_checks"), list)

