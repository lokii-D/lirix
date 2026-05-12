# ruff: noqa: E501
#!/usr/bin/env python3
"""Print CV score panel from docs/cv_rubric.yaml (optional --enforce for exit 1 if < 95).

Per-dimension lines include each automated check; **test_change_safety** includes
``contributing_local_tests_doc`` when ``docs/contributing_local_tests.md`` is present (see rubric).
**ci_alignment** includes ``tools_gates_index_doc`` when ``docs/tools_gates_index.md`` exists.
Automated check ``points`` are intended to sum to each dimension's ``weight``; if they differ,
the report scales dimension scores to the weight (see each dimension's "Dimension scaled score").
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUBRIC_PATH = ROOT / "docs" / "cv_rubric.yaml"


def _path_exists(rel: str) -> bool:
    return (ROOT / rel).is_file() or (ROOT / rel).is_dir()


def _file_contains(rel: str, needles: list[str]) -> bool:
    path = ROOT / rel
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return all(n in text for n in needles)


def _eval_check(spec: dict[str, Any]) -> tuple[int, int, list[str]]:
    """Return (awarded, possible, notes)."""
    points = int(spec.get("points", 0))
    notes: list[str] = []
    if "require_paths" in spec:
        rels: list[str] = list(spec["require_paths"])
        ok = all(_path_exists(r) for r in rels)
        if ok:
            return points, points, notes
        missing = [r for r in rels if not _path_exists(r)]
        notes.append(f"missing paths: {missing}")
        return 0, points, notes
    if "require_strings_in_file" in spec:
        cfg = spec["require_strings_in_file"]
        rel = str(cfg["file"])
        needles = list(cfg["needles"])
        if _file_contains(rel, [str(n) for n in needles]):
            return points, points, notes
        notes.append(f"strings not all found in {rel}")
        return 0, points, notes
    notes.append("unknown check shape")
    return 0, points, notes


def _eval_vetoes(dimensions: list[dict[str, Any]]) -> list[str]:
    """Return human-readable veto messages (missing_path style only)."""
    messages: list[str] = []
    for dim in dimensions:
        dim_id = str(dim.get("id", "?"))
        for spec in list(dim.get("veto_if", []) or []):
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name", "veto"))
            rel = spec.get("missing_path")
            if isinstance(rel, str) and not _path_exists(rel):
                messages.append(f"{dim_id}/{name}: missing {rel}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit 1 when total score < 95 or a rubric veto fires (strict lanes only).",
    )
    args = parser.parse_args()

    if not RUBRIC_PATH.is_file():
        print(f"cv_score_report: missing {RUBRIC_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 2

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        print(
            "cv_score_report: PyYAML is not installed. Install dev dependencies in your venv, e.g.\n"
            '  python -m pip install -e ".[dev]"\n'
            "or: python -m pip install pyyaml\n"
            f"(rubric file present at {RUBRIC_PATH.relative_to(ROOT)} but cannot be parsed.)",
            file=sys.stderr,
        )
        return 2

    data = yaml.safe_load(RUBRIC_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("cv_score_report: rubric YAML root must be a mapping", file=sys.stderr)
        return 2
    rubric_version = data.get("version")
    dimensions: list[dict[str, Any]] = list(data.get("dimensions", []))
    veto_msgs = _eval_vetoes(dimensions)

    total_awarded = 0
    total_possible = 0
    lines: list[str] = []
    lines.append("Lirix CV score report (automated band)")
    lines.append(f"Rubric: {RUBRIC_PATH.relative_to(ROOT)}")
    lines.append(f"Rubric version: {rubric_version!r} (from YAML `version:`)")
    lines.append("")

    for dim in dimensions:
        dim_id = str(dim.get("id", "?"))
        name = str(dim.get("name", dim_id))
        weight = int(dim.get("weight", 0))
        checks = list(dim.get("automated_checks", []))
        dim_possible = sum(int(c.get("points", 0)) for c in checks)
        dim_awarded = 0
        lines.append(f"## {name} ({dim_id}) — weight {weight}")
        if dim_possible != weight:
            lines.append(f"  (note: automated subtotal {dim_possible} vs weight {weight})")
        for chk in checks:
            cid = str(chk.get("id", "?"))
            awarded, possible, notes = _eval_check(chk)
            dim_awarded += awarded
            status = "OK" if awarded == possible else "MISS"
            lines.append(f"  - [{status}] {cid}: {awarded}/{possible}")
            for n in notes:
                lines.append(f"      {n}")
        # Scale dimension score to weight when automated subtotal differs
        if dim_possible > 0 and dim_possible != weight:
            scaled = round(dim_awarded * weight / dim_possible)
        else:
            scaled = dim_awarded
        total_awarded += scaled
        total_possible += weight
        lines.append(f"  Dimension scaled score: {scaled} / {weight}")
        lines.append("")

    lines.append(f"TOTAL (scaled to rubric weights): {total_awarded} / {total_possible}")
    if veto_msgs:
        lines.append("")
        lines.append("VETO (missing_path checks)")
        for m in veto_msgs:
            lines.append(f"  - {m}")
    print("\n".join(lines))

    if veto_msgs and args.enforce:
        print("cv_score_report: --enforce failed (rubric veto)", file=sys.stderr)
        return 1
    if args.enforce and total_awarded < 95:
        print("cv_score_report: --enforce failed (score < 95)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
