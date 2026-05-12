from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_no_internal_imports_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "no-internal-imports"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "CI": "true"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_no_internal_imports_gate_rejects_new_import(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"

    sandbox = tmp_path / "scan"
    sandbox.mkdir()
    bad = sandbox / "bad.py"
    bad.write_text("import lirix._client_core\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(tool), "no-internal-imports"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "NO_INTERNAL_IMPORTS_SCAN_DIRS": str(sandbox),
            "NO_INTERNAL_IMPORTS_SCAN_FILES": "",
        },
    )
    assert proc.returncode != 0
