from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_plan_to_pr_exit_metrics_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "plan-to-pr-exit-metrics"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
