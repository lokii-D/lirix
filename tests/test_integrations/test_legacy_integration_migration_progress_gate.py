from __future__ import annotations

from pathlib import Path


def test_legacy_integration_migration_progress_gate() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    legacy_dir = repo_root / "tests" / "integrations"
    canonical_dir = repo_root / "tests" / "test_integrations"
    legacy_py = sorted(p.name for p in legacy_dir.glob("test_*.py"))
    canonical_py = sorted(canonical_dir.glob("test_*.py"))

    assert legacy_py == [], "tests/integrations must be empty after canonical migration"

    # Canonical directory remains the growth surface for new integration tests.
    assert len(canonical_py) >= 10
