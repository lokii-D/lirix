# ruff: noqa: E501
# mypy: ignore-errors
#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
PACKAGE_DIR = ROOT / "lirix"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"

OUT_DIR = Path(
    os.environ.get(
        "MIGRATION_OBS_OUT_DIR", str(ROOT / "audit_artifacts" / "migration_observability")
    )
)
PREVIOUS_JSON = Path(os.environ.get("MIGRATION_OBS_PREVIOUS_PATH", str(OUT_DIR / "previous.json")))
EXCLUDED_SOURCE_PARTS = (
    ".git",
    ".tox",
    "build",
    "dist",
    "site-packages",
)


def _is_source_path(path: Path) -> bool:
    return not any(part.startswith(".venv") or part in EXCLUDED_SOURCE_PARTS for part in path.parts)


def _collect_python_files(root: Path, *, source_only: bool) -> list[Path]:
    files = (p for p in root.rglob("*.py") if p.is_file())
    if source_only:
        return sorted(p for p in files if _is_source_path(p))
    return sorted(files)


def _count_compat_imports() -> dict[str, Any]:
    compat_keys = ("lirix._client_core", "lirix.core")

    def _scan(files: list[Path]) -> dict[str, list[str]]:
        hits: dict[str, list[str]] = {key: [] for key in compat_keys}
        for path in files:
            text = path.read_text(encoding="utf-8")
            for key in hits:
                if f"from {key}" in text or f"import {key}" in text:
                    hits[key].append(str(path.relative_to(ROOT)))
        return hits

    source_hits = _scan(_collect_python_files(ROOT, source_only=True))
    full_hits = _scan(_collect_python_files(ROOT, source_only=False))
    noise_hits = {key: sorted(set(full_hits[key]) - set(source_hits[key])) for key in compat_keys}

    return {
        "source_only": {
            "counts": {k: len(v) for k, v in source_hits.items()},
            "files": {k: sorted(v) for k, v in source_hits.items()},
        },
        "artifact_noise": {
            "counts": {k: len(v) for k, v in noise_hits.items()},
            "files": {k: sorted(v) for k, v in noise_hits.items()},
        },
        "scan_policy": {
            "excluded_path_parts": list(EXCLUDED_SOURCE_PARTS) + [".venv*"],
        },
    }


def _test_fragmentation_snapshot() -> dict[str, Any]:
    files = _collect_python_files(TESTS_DIR, source_only=True)
    test_files = [p for p in files if p.name.startswith("test_")]
    micro_files: list[str] = []
    for path in test_files:
        text = path.read_text(encoding="utf-8")
        count = sum(1 for line in text.splitlines() if line.lstrip().startswith("def test_"))
        if count <= 1:
            micro_files.append(str(path.relative_to(ROOT)))
    total = len(test_files)
    micro_count = len(micro_files)
    return {
        "test_files": total,
        "micro_files": micro_count,
        "micro_ratio": round((micro_count / total), 4) if total else 0.0,
        "micro_file_examples": micro_files[:20],
    }


def _entry_surface_snapshot() -> dict[str, Any]:
    init_file = PACKAGE_DIR / "__init__.py"
    text = init_file.read_text(encoding="utf-8")
    exports = sorted(
        {
            line.split('"')[1]
            for line in text.splitlines()
            if line.strip().startswith('"') and line.strip().endswith('",')
        }
    )
    return {
        "canonical_module": "lirix",
        "root_exports": exports,
        "root_export_count": len(exports),
    }


def _count_test_markers() -> dict[str, int]:
    marker_counts = {"slow": 0, "e2e": 0, "network": 0, "perf": 0, "migration": 0}
    for path in _collect_python_files(TESTS_DIR, source_only=True):
        if not path.name.startswith("test_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            for dec in node.decorator_list:
                if (
                    isinstance(dec, ast.Attribute)
                    and isinstance(dec.value, ast.Attribute)
                    and isinstance(dec.value.value, ast.Name)
                    and dec.value.value.id == "pytest"
                    and dec.value.attr == "mark"
                    and dec.attr in marker_counts
                ):
                    marker_counts[dec.attr] += 1
    return marker_counts


def _extract_workflow_snapshot() -> dict[str, Any]:
    ci_path = WORKFLOWS_DIR / "ci.yml"
    ci_text = ci_path.read_text(encoding="utf-8") if ci_path.is_file() else ""
    has_schedule_on_main_ci = "schedule:" in ci_text
    compatibility_expr = ""
    for line in ci_text.splitlines():
        if "pytest -q -m " in line:
            compatibility_expr = line.strip()
    slow_workflows = []
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        if "slow or e2e or network or perf" in text:
            slow_workflows.append(str(wf.relative_to(ROOT)))
    return {
        "main_ci_has_schedule": has_schedule_on_main_ci,
        "compatibility_marker_expression": compatibility_expr,
        "slow_lane_workflows": slow_workflows,
    }


def _load_previous_payload() -> dict[str, Any] | None:
    if not PREVIOUS_JSON.is_file():
        return None
    try:
        return json.loads(PREVIOUS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _trend(
    curr: dict[str, Any], prev: dict[str, Any] | None, keys: Iterable[str]
) -> dict[str, int]:
    out: dict[str, int] = {}
    for key in keys:
        current = int(curr.get(key, 0))
        before = int((prev or {}).get(key, 0))
        out[key] = current - before
    return out


def _payload_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _integrity_snapshot(
    *,
    payload_without_integrity: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    previous_integrity = (previous or {}).get("integrity")
    previous_has_integrity = isinstance(previous_integrity, dict)
    previous_digest = (
        _payload_digest({k: v for k, v in (previous or {}).items() if k != "integrity"})
        if previous
        else None
    )
    previous_claimed = (
        str(previous_integrity.get("snapshot_payload_sha256")) if previous_has_integrity else None
    )
    return {
        "snapshot_payload_sha256": _payload_digest(payload_without_integrity),
        "previous_available": previous is not None,
        "previous_has_integrity": previous_has_integrity,
        "previous_snapshot_sha256": previous_claimed,
        "previous_snapshot_sha256_verified": bool(
            previous and previous_has_integrity and previous_claimed == previous_digest
        ),
    }


def _render_markdown(payload: dict[str, object]) -> str:
    ci = payload["ci_workflows"]
    tests = payload["tests"]
    compat_source = payload["compat_import_hits"]["source_only"]
    compat_noise = payload["compat_import_hits"]["artifact_noise"]
    trends = payload["trends"]
    return "\n".join(
        [
            "# Migration Observability Report",
            "",
            f"- Generated at: `{payload['generated_at_utc']}`",
            "",
            "## API Surface",
            f"- Canonical module: `{payload['entry_surface']['canonical_module']}`",
            f"- Root export count: `{payload['entry_surface']['root_export_count']}`",
            f"- Compatibility import counts (source-only): `{compat_source['counts']}`",
            f"- Compatibility import counts (artifact-noise): `{compat_noise['counts']}`",
            "",
            "## CI Routing",
            f"- Main CI has schedule trigger: `{ci['main_ci_has_schedule']}`",
            f"- Compatibility marker expression: `{ci['compatibility_marker_expression']}`",
            f"- Slow lane workflows: `{ci['slow_lane_workflows']}`",
            "",
            "## Marker Coverage",
            f"- Marker counts: `{payload['test_markers']}`",
            "",
            "## Test Topology",
            f"- Test files: `{tests['test_files']}`",
            f"- Micro files (<=1 test): `{tests['micro_files']}`",
            f"- Micro ratio: `{tests['micro_ratio']}`",
            "",
            "## Trends vs Previous",
            f"- Root export delta: `{trends['entry_surface']}`",
            f"- Compat import delta: `{trends['compat_import_hits']}`",
            f"- Test topology delta: `{trends['tests']}`",
            "",
            "## Snapshot Integrity",
            f"- Snapshot payload digest: `{payload['integrity']['snapshot_payload_sha256']}`",
            f"- Previous snapshot available: `{payload['integrity']['previous_available']}`",
            f"- Previous integrity present: `{payload['integrity']['previous_has_integrity']}`",
            f"- Previous digest verified: `{payload['integrity']['previous_snapshot_sha256_verified']}`",
        ]
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    previous = _load_previous_payload()
    compat = _count_compat_imports()
    tests_snapshot = _test_fragmentation_snapshot()
    entry_surface = _entry_surface_snapshot()
    payload_without_integrity: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "entry_surface": entry_surface,
        "compat_import_hits": compat,
        "ci_workflows": _extract_workflow_snapshot(),
        "test_markers": _count_test_markers(),
        "tests": tests_snapshot,
        "trends": {
            "entry_surface": _trend(
                {"root_export_count": entry_surface["root_export_count"]},
                (previous or {}).get("entry_surface") if previous else None,
                ["root_export_count"],
            ),
            "compat_import_hits": _trend(
                compat["source_only"]["counts"],
                (previous or {}).get("compat_import_hits", {}).get("source_only", {}).get("counts"),
                compat["source_only"]["counts"].keys(),
            ),
            "tests": _trend(
                {
                    "test_files": tests_snapshot["test_files"],
                    "micro_files": tests_snapshot["micro_files"],
                },
                (previous or {}).get("tests") if previous else None,
                ["test_files", "micro_files"],
            ),
        },
    }
    payload: dict[str, object] = dict(payload_without_integrity)
    payload["integrity"] = _integrity_snapshot(
        payload_without_integrity=payload_without_integrity,
        previous=previous,
    )

    integrity = payload["integrity"]
    ci_mode = os.environ.get("CI") in {"1", "true", "True"}
    if (
        ci_mode
        and integrity["previous_available"]
        and integrity["previous_has_integrity"]
        and not integrity["previous_snapshot_sha256_verified"]
    ):
        print(
            "observability-integrity: fail-closed (previous snapshot integrity present but not verified)"
        )
        return 1
    out_prev = OUT_DIR / "previous.json"
    out_json = OUT_DIR / "latest.json"
    out_md = OUT_DIR / "latest.md"
    if out_json.is_file():
        out_prev.write_text(out_json.read_text(encoding="utf-8"), encoding="utf-8")
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(payload) + "\n", encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
