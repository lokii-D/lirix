from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_module():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "tools" / "release_acceptance_report.py"
    spec = importlib.util.spec_from_file_location("release_acceptance_report", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_metrics_quiet_pytest_last_summary_line() -> None:
    mod = _load_module()
    text = "\nsome noise\n\n879 passed, 2 skipped, 0 warnings in 42.00s\n"
    m = mod._extract_metrics(text)
    assert m["passed"] == 879
    assert m["failed"] == 0
    assert m["warnings"] == 0


def test_extract_metrics_banner_and_coverage_total() -> None:
    mod = _load_module()
    text = """
============================= test session starts ==============================
foo
=================================== 12 passed in 1.00s ===================================
Name                          Stmts   Miss  Cover
-------------------------------------------------
lirix/__init__.py                10      0   100%
-------------------------------------------------
TOTAL                            10      0   100%
"""
    m = mod._extract_metrics(text)
    assert m["passed"] == 12
    assert m["failed"] == 0
    assert m["coverage_percent"] == 100.0


def test_infer_signoff_dir_from_log_path() -> None:
    mod = _load_module()
    root = Path(__file__).resolve().parents[2]
    log = root / "audit_artifacts" / "release_signoff" / "2099-01-01" / "B4_pytest.log"
    inferred = mod._infer_signoff_dir(log)
    assert inferred == root / "audit_artifacts" / "release_signoff" / "2099-01-01"


def test_infer_signoff_dir_none_when_not_under_release_signoff() -> None:
    mod = _load_module()
    assert mod._infer_signoff_dir(Path("/tmp/pytest.log")) is None


def test_collect_recommended_artifact_hints_no_signoff_dir() -> None:
    mod = _load_module()
    h = mod._collect_recommended_artifact_hints(None)
    assert h["signoff_dir"] is None
    assert "note" in h


def test_collect_recommended_artifact_hints_with_files(tmp_path: Path) -> None:
    mod = _load_module()
    d = tmp_path / "bundle"
    d.mkdir()
    (d / "B4_real_e2e_ci.log").write_text("ok\n", encoding="utf-8")
    (d / "B4_perf_baseline_x.json").write_text("{}", encoding="utf-8")
    (d / "B4_perf_baseline_x.normalized.json").write_text("{}", encoding="utf-8")
    brief = d / "B4_local_ci_equivalent_brief.md"
    brief.write_text("E2E_SKIP_REASON=not run\n", encoding="utf-8")
    h = mod._collect_recommended_artifact_hints(d)
    assert h["signoff_dir"] == str(d.resolve())
    assert h["real_e2e_log_present"] is True
    assert h["perf_raw_json_present"] is True
    assert h["perf_normalized_json_present"] is True
    assert h["e2e_skip_reason_documented_in_brief"] is True
    assert h["brief_checked"] == "B4_local_ci_equivalent_brief.md"


def test_collect_recommended_artifact_hints_brief_without_skip_marker(tmp_path: Path) -> None:
    mod = _load_module()
    d = tmp_path / "b"
    d.mkdir()
    (d / "B4_local_ci_equivalent_brief.md").write_text("no marker here\n", encoding="utf-8")
    h = mod._collect_recommended_artifact_hints(d)
    assert h["e2e_skip_reason_documented_in_brief"] is False


def test_collect_recommended_artifact_hints_not_a_directory(tmp_path: Path) -> None:
    mod = _load_module()
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    h = mod._collect_recommended_artifact_hints(f)
    assert h.get("error") == "not_a_directory"


def test_main_cli_json_release_ok(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "release_acceptance_report.py"
    log = tmp_path / "cov.log"
    log.write_text(
        "900 passed, 0 warnings in 1s\nTOTAL                          100      0   100%\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--log",
            str(log),
            "--coverage-threshold",
            "100",
            "--warnings-blocking",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout.strip())
    assert out["evaluation"]["release_ok"] is True
