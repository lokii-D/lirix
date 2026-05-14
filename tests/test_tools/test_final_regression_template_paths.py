from __future__ import annotations

import re
from pathlib import Path


def test_final_regression_template_references_existing_test_paths() -> None:
    """Release regression shell template must not drift to non-existent modules."""
    root = Path(__file__).resolve().parents[2]
    script = (root / "tools" / "final_regression_template.sh").read_text(encoding="utf-8")
    paths = sorted(set(re.findall(r"tests/[a-zA-Z0-9_/]+\.py", script)))
    assert paths, "expected at least one tests/...py path in final_regression_template.sh"
    missing = [p for p in paths if not (root / p).is_file()]
    assert not missing, f"final_regression_template.sh references missing paths: {missing}"
