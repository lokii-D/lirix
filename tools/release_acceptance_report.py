# mypy: ignore-errors
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional

PYTEST_SUMMARY_RE = re.compile(r"=+\s*(?P<summary>.+?)\s*=+")
PASSED_RE = re.compile(r"(?P<passed>\d+)\s+passed")
FAILED_RE = re.compile(r"(?P<failed>\d+)\s+failed")
WARNING_RE = re.compile(r"(?P<warnings>\d+)\s+warnings?")
# Coverage.py summary table can have varying column counts depending on configuration
# (e.g., with/without branch coverage). We only need the final TOTAL percentage.
COVERAGE_RE = re.compile(r"TOTAL\s+(?:\d+\s+)+(?P<coverage>\d+(?:\.\d+)?)%")


def _extract_metrics(text: str) -> dict[str, Any]:
    pytest_summary = ""
    for line in text.splitlines():
        m = PYTEST_SUMMARY_RE.search(line)
        if m and ("passed" in m.group("summary") or "failed" in m.group("summary")):
            pytest_summary = m.group("summary")
    # Quiet runs (e.g. ``pytest -q``) often omit the ``====`` banner; use the last "N passed" line.
    if not pytest_summary:
        for line in reversed(text.splitlines()):
            stripped = line.strip()
            if PASSED_RE.search(stripped) or FAILED_RE.search(stripped):
                pytest_summary = stripped
                break
    passed_match = PASSED_RE.search(pytest_summary)
    passed = int(passed_match.group("passed")) if passed_match else 0

    failed_match = FAILED_RE.search(pytest_summary)
    failed = int(failed_match.group("failed")) if failed_match else 0
    warnings = (
        int(WARNING_RE.search(pytest_summary).group("warnings"))
        if WARNING_RE.search(pytest_summary)
        else 0
    )
    coverage_match = COVERAGE_RE.search(text)
    coverage = float(coverage_match.group("coverage")) if coverage_match else None
    return {
        "pytest_summary": pytest_summary,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "coverage_percent": coverage,
    }


def _infer_signoff_dir(log_path: Path) -> Optional[Path]:
    """If the log lives under ``.../release_signoff/<date>/``, return that date folder."""
    resolved = log_path.resolve()
    parts = resolved.parts
    if "release_signoff" not in parts:
        return None
    idx = parts.index("release_signoff")
    if idx + 1 >= len(parts):
        return None
    return Path(*parts[: idx + 2])


def _collect_recommended_artifact_hints(signoff_dir: Optional[Path]) -> dict[str, Any]:
    """Non-blocking hints for human review (does not affect ``release_ok``)."""
    if signoff_dir is None:
        return {
            "signoff_dir": None,
            "note": (
                "pass --signoff-dir or place the log under "
                "audit_artifacts/release_signoff/<date>/ to scan"
            ),
        }
    d = signoff_dir.resolve()
    if not d.is_dir():
        return {"signoff_dir": str(d), "error": "not_a_directory"}

    e2e_logs = sorted(d.glob("B4_real_e2e*.log"))
    norm_perf = sorted(d.glob("*.normalized.json"))
    norm_perf = [p for p in norm_perf if "perf" in p.name.lower() or "baseline" in p.name.lower()]
    raw_perf = sorted(
        p for p in d.glob("B4_perf_baseline*.json") if not p.name.endswith(".normalized.json")
    )
    brief = d / "B4_local_ci_equivalent_brief.md"
    brief_has_skip = False
    if brief.is_file():
        brief_has_skip = "E2E_SKIP_REASON" in brief.read_text(encoding="utf-8")

    return {
        "signoff_dir": str(d),
        "real_e2e_log_present": bool(e2e_logs),
        "real_e2e_log_files": [p.name for p in e2e_logs],
        "perf_normalized_json_present": bool(norm_perf),
        "perf_normalized_json_files": [p.name for p in norm_perf],
        "perf_raw_json_present": bool(raw_perf),
        "perf_raw_json_files": [p.name for p in raw_perf],
        "e2e_skip_reason_documented_in_brief": brief_has_skip,
        "brief_checked": brief.name if brief.is_file() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a single-source acceptance report from pytest full coverage log."
    )
    parser.add_argument("--log", required=True, help="Path to pytest full coverage log.")
    parser.add_argument(
        "--coverage-threshold",
        type=float,
        default=100.0,
        help="Coverage threshold for release pass/fail evaluation.",
    )
    parser.add_argument(
        "--warnings-blocking",
        action="store_true",
        help="Treat warnings > 0 as blocking.",
    )
    parser.add_argument(
        "--signoff-dir",
        type=Path,
        default=None,
        help=(
            "Optional release sign-off date folder (audit_artifacts/release_signoff/<date>) "
            "to scan for recommended E2E/perf artifacts."
        ),
    )
    args = parser.parse_args()

    log_path = Path(args.log)
    text = log_path.read_text(encoding="utf-8")
    metrics = _extract_metrics(text)
    coverage_ok = metrics["coverage_percent"] is not None and float(
        metrics["coverage_percent"]
    ) >= float(args.coverage_threshold)
    warnings_ok = (metrics["warnings"] == 0) or (not args.warnings_blocking)
    release_ok = metrics["failed"] == 0 and coverage_ok and warnings_ok
    signoff_dir = args.signoff_dir if args.signoff_dir is not None else _infer_signoff_dir(log_path)
    report = {
        "log": str(log_path),
        "criteria": {
            "coverage_threshold": args.coverage_threshold,
            "warnings_blocking": args.warnings_blocking,
        },
        "metrics": metrics,
        "recommended_artifacts_present": _collect_recommended_artifact_hints(signoff_dir),
        "evaluation": {
            "failed_tests_ok": metrics["failed"] == 0,
            "coverage_ok": coverage_ok,
            "warnings_ok": warnings_ok,
            "release_ok": release_ok,
        },
    }
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if release_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
