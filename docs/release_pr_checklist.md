# Release PR checklist (maintainer)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

Use this list when opening or reviewing a **version / release** pull request. Authoritative procedures and command snippets live in [`audit_artifacts/release_signoff/README.md`](../audit_artifacts/release_signoff/README.md).

## One-command local rehearsal

From a clean venv with `pip install -e ".[dev]"`, run the fixed-order chain (matches **`.github/workflows/ci.yml`** `lint` job semantics, then full `pytest` + acceptance JSON):

```bash
bash tools/release_full_verification.sh
```

For the concise final-regression command set (A/B/C/D/E checklist), run:

```bash
bash tools/final_regression_template.sh
```

- Logs and acceptance JSON default to `audit_artifacts/release_signoff/<today>/` (override with `RELEASE_SIGNOFF_OUT=/path/to/dir`).
- Optional real E2E: start Anvil (or rely on your environment), then `RUN_ANVIL_E2E=1 bash tools/release_full_verification.sh`. Use `RUN_ANVIL_E2E_STRICT=1` if E2E failures must fail the script.
- **CI differences:** GitHub **test** matrix runs `python -m pytest tests/` on multiple OS/Python versions and starts Anvil for those jobs; this script runs **one** local interpreter and does **not** start Anvil unless you opt in. Optional workflow [`.github/workflows/e2e-anvil-optional.yml`](../.github/workflows/e2e-anvil-optional.yml) uploads E2E logs as artifacts for audit alignment.
- **Doc preamble gate:** `python tools/harness.py doc-preamble-hygiene` is part of **Fast Required** and **governance-lane** in CI (**warn-only**; use `--enforce` locally to fail on drift).

## Must-have (blocking)

- [ ] **Full pytest + coverage log** under `audit_artifacts/release_signoff/<YYYY-MM-DD>/`, e.g. `B4_pytest_full_cov*.log`, with **`[tool.coverage.report].fail_under = 100`** satisfied for `lirix/`.
- [ ] **Acceptance JSON** from `tools/release_acceptance_report.py` with **`--coverage-threshold 100`** and **`--warnings-blocking`** (committed as `B4_release_acceptance_report_*.json` in the same date folder). The JSON must show `evaluation.release_ok: true`.
- [ ] **Minimum evidence set** described in the signoff README (briefs, governance log, warnings baseline log, release notes gate logs, etc.) present under that date folder.

## Recommended (non-blocking but release-grade)

- [ ] **Real Anvil E2E log** (`B4_real_e2e*.log`) **or** explicit skip documented in `B4_local_ci_equivalent_brief.md` with `E2E_SKIP_REASON=...` (see signoff README § Real E2E).
- [ ] **Performance baseline** (optional JSON): raw and/or `.normalized.json` per signoff README § Performance baseline.

## Machine-readable hints

After generating the acceptance report, open the JSON field **`recommended_artifacts_present`**: it flags whether typical E2E and perf filenames were found in the sign-off directory (inferred from the log path or `--signoff-dir`). This does **not** change `release_ok`; it is for reviewer visibility only.
