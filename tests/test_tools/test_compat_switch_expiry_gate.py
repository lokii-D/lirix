from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _gate_env(root: Path) -> dict[str, str]:
    prev = os.environ.get("PYTHONPATH", "")
    merged = str(root) + (os.pathsep + prev if prev else "")
    return {**os.environ, "PYTHONPATH": merged}


def test_compat_switch_expiry_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "compat-switch-expiry"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env=_gate_env(root),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_compat_switch_expiry_gate_fails_after_expiry_when_compat_path_reachable() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "compat-switch-expiry"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={**_gate_env(root), "LIRIX_COMPAT_GATE_TODAY": "2026-07-01"},
    )
    assert proc.returncode == 1
    assert "compat-switch expired" in (proc.stdout + proc.stderr)


def test_compat_switch_expiry_gate_passes_before_expiry_with_overridden_today() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "compat-switch-expiry"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={**_gate_env(root), "LIRIX_COMPAT_GATE_TODAY": "2026-06-01"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
