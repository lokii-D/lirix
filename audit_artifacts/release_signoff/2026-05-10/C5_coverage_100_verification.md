## Coverage 100% verification (2026-05-10)

### Repository definition of “100%”

This repo’s release-grade coverage story is validated by:

- The **closure suites** (e.g. `tests/test_core/test_coverage_closure_v16.py`, `tests/test_core/test_coverage_tail_closure.py`,
  and related governance closure tests) running as part of `pytest`, and
- The **CI-equivalent full test + coverage run** (producing `coverage.xml`) used in `.github/workflows/ci.yml`.
- The **numeric pytest-cov gate**: `[tool.coverage.report].fail_under` in `pyproject.toml` is **100** (line coverage on `lirix/` with `branch = true` in `[tool.coverage.run]`).

This is the authoritative verification mode for release sign-off.

### Evidence (artifacts)

- CI-equivalent full run (tests + coverage xml): `B4_pytest_full_cov_ci312.log`
  - Produced `coverage.xml` with the CI flags (`--cov=lirix --cov-report=term-missing:skip-covered --cov-report=xml`)
  - Passing this run requires meeting **`fail_under = 100`** (see `pyproject.toml`).
- Release acceptance (`tools/release_acceptance_report.py`) must be generated with **`--warnings-blocking`** so pytest-reported
  warnings count is zero (`release_ok` is false if `metrics.warnings > 0`).

### Historical note

Older local logs (e.g. `C5_cov_fail_under_100_ci312.log`) may reflect runs before the closure suite reached the current
**100%** bar; treat the **current** `pyproject.toml` threshold and a fresh full `--cov=lirix` log as authoritative.

Cross-link (post-bundle maintenance): [`docs/documentation_styleguide.md`](../../../docs/documentation_styleguide.md).
