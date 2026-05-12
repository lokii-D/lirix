from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_migration_observability_scan_policy_exclusions_are_contracted() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "migration_observability_report.py"
    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    payload = json.loads((root / "audit_artifacts" / "migration_observability" / "latest.json").read_text(encoding="utf-8"))
    excluded = payload["compat_import_hits"]["scan_policy"]["excluded_path_parts"]
    assert excluded == [".git", ".tox", "build", "dist", "site-packages", ".venv*"]

    doc = (root / "docs" / "migration_observability_scan_policy.md").read_text(encoding="utf-8")
    for needle in excluded:
        assert needle in doc

