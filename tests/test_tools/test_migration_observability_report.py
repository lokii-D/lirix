from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_migration_observability_report_emits_integrity_and_split_metrics() -> None:
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
    payload = json.loads(
        (root / "audit_artifacts" / "migration_observability" / "latest.json").read_text(
            encoding="utf-8"
        )
    )
    assert "integrity" in payload
    assert "source_only" in payload["compat_import_hits"]
    assert "artifact_noise" in payload["compat_import_hits"]


def test_migration_observability_report_fail_closed_on_tampered_previous(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "migration_observability_report.py"

    out_dir = tmp_path / "obs"
    out_dir.mkdir()
    previous = out_dir / "previous.json"

    # Claimed digest does not match actual payload -> verified=false.
    previous.write_text(
        json.dumps(
            {
                "entry_surface": {"canonical_module": "lirix", "root_export_count": 1, "root_exports": []},
                "compat_import_hits": {"source_only": {"counts": {}}, "artifact_noise": {"counts": {}}, "scan_policy": {"excluded_path_parts": []}},
                "ci_workflows": {"main_ci_has_schedule": False, "compatibility_marker_expression": "", "slow_lane_workflows": []},
                "test_markers": {"slow": 0, "e2e": 0, "network": 0, "perf": 0, "migration": 0},
                "tests": {"test_files": 1, "micro_files": 0, "micro_ratio": 0.0, "micro_file_examples": []},
                "trends": {"entry_surface": {"root_export_count": 0}, "compat_import_hits": {}, "tests": {"test_files": 0, "micro_files": 0}},
                "generated_at_utc": "2000-01-01T00:00:00+00:00",
                "integrity": {"snapshot_payload_sha256": "deadbeef"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(tool)],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "CI": "true",
            "MIGRATION_OBS_OUT_DIR": str(out_dir),
            "MIGRATION_OBS_PREVIOUS_PATH": str(previous),
        },
    )
    assert proc.returncode != 0
