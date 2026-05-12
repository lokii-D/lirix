from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _validate_metrics(obj: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_top = ("schema_version", "profile", "metrics")
    for key in required_top:
        if key not in obj:
            errors.append(f"missing top-level key: {key}")
    metrics = obj.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("metrics must be an object")
        return errors
    for path in (
        ("validate_only_ms", "p50"),
        ("validate_only_ms", "p95"),
        ("validate_and_simulate_ms", "p50"),
        ("validate_and_simulate_ms", "p95"),
        ("simulate_only_ms", "p50"),
        ("simulate_only_ms", "p95"),
        ("concurrent_error_rate",),
    ):
        cur: Any = metrics
        for part in path:
            if not isinstance(cur, dict) or part not in cur:
                errors.append(f"metrics missing path: {'.'.join(path)}")
                cur = None
                break
            cur = cur.get(part)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and normalize a perf baseline JSON artifact for release sign-off.",
    )
    parser.add_argument("--json", required=True, type=Path, help="Path to perf baseline JSON.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write canonical JSON (sorted keys).",
    )
    args = parser.parse_args()

    raw = args.json.read_text(encoding="utf-8")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Invalid JSON: {exc}\n")
        return 2

    if not isinstance(obj, dict):
        sys.stderr.write("Root JSON value must be an object.\n")
        return 2

    errors = _validate_metrics(obj)
    if errors:
        sys.stderr.write("PERF BASELINE SCHEMA FAILED\n")
        for line in errors:
            sys.stderr.write(f"- {line}\n")
        return 3

    canonical = json.dumps(obj, ensure_ascii=True, sort_keys=True, indent=2)
    if args.out is not None:
        args.out.write_text(canonical + "\n", encoding="utf-8")
    else:
        sys.stdout.write(canonical + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
