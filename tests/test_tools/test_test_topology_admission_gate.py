from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_test_topology_admission_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "test-topology-admission"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_test_topology_admission_gate_baseline_precedence(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"

    # Make previous.json unusable but baseline readable; gate must still pass.
    previous = tmp_path / "previous.json"
    previous.write_text("{", encoding="utf-8")

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"tests": {"micro_ratio": 1.0}}) + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(tool), "test-topology-admission"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "TEST_TOPOLOGY_BASELINE_PATH": str(baseline),
            "TEST_TOPOLOGY_PREVIOUS_PATH": str(previous),
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
