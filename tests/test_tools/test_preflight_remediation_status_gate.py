from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_preflight_remediation_status_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "preflight-remediation-status"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_preflight_remediation_contract_json_loads() -> None:
    import json

    root = Path(__file__).resolve().parents[2]
    path = root / "tools" / "preflight_remediation_contract.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert any(r.get("id") == "R-001" for r in data.get("rules", []))
