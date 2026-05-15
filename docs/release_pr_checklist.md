# Release PR checklist (maintainer)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

Use this list when opening or reviewing a **version / release** pull request. Authoritative procedures and command snippets live in [`audit_artifacts/release_signoff/README.md`](../audit_artifacts/release_signoff/README.md). For the **final redundant multiscan agent harness** (waves A–L, handoff template, repo fingerprint), see [`release_final_multiscan_harness_r3.md`](release_final_multiscan_harness_r3.md).

## Local CI-equivalent rehearsal

**Python 3.12** is the **authoritative** interpreter for release sign-off (matches `.python-version` and `ci.yml`); personal newer runtimes are exploratory only until gates are replayed on 3.12.

**Work tree:** before tagging or opening a release PR, `git status --short` must show **no unintended** `??` deliverables and no surprise `MM` splits — the Git object graph is the auditable release surface (see `python tools/harness.py preflight-remediation-status` for R-002-style hazards).

**Full `pytest` skips (charter):** a default full-tree `pytest -q -rs` run may list **four** skips from `tests/test_core/test_pipeline_performance_gates.py` (perf baseline env) and `tests/test_integration/test_real_e2e_paths.py` (live RPC / Anvil). That is **expected** for default CI and local venvs; closing them is **optional** evidence (perf JSON, Anvil E2E log) per § **Recommended** below and `docs/ci_gate_matrix.md` § **Full default collection — expected `pytest` skips**.

Local shell wrappers that duplicated CI have been removed. From a clean venv with `pip install -e ".[dev]"`, mirror **`.github/workflows/ci.yml`** and capture logs under `audit_artifacts/release_signoff/<today>/` using the step-by-step **`tee`** block in [`audit_artifacts/release_signoff/README.md`](../audit_artifacts/release_signoff/README.md) § **How to generate (local CI-equivalent replay)** (set `OUT` / `RELEASE_SIGNOFF_OUT` as documented there). After Fast Required semantics, run `python tools/harness.py test-coverage-required` and `python tools/release_acceptance_report.py` as in that README.

For the concise final-regression command set (A/B/C/D/E checklist), run:

```bash
bash tools/final_regression_template.sh
```

- Logs and acceptance JSON default to `audit_artifacts/release_signoff/<today>/` (override with `RELEASE_SIGNOFF_OUT=/path/to/dir`).
- Optional real E2E: start Anvil (or rely on your environment), then `RUN_ANVIL_E2E=1 python -m pytest -o addopts= -q tests/test_integration/test_real_e2e_paths.py`. For hard failure on E2E errors, run under `set -e` or rely on [`.github/workflows/e2e-anvil-optional.yml`](../.github/workflows/e2e-anvil-optional.yml) in CI.
- **CI differences:** GitHub **test** matrix runs `python -m pytest tests/` on multiple OS/Python versions and starts Anvil for those jobs; this script runs **one** local interpreter and does **not** start Anvil unless you opt in. Optional workflow [`.github/workflows/e2e-anvil-optional.yml`](../.github/workflows/e2e-anvil-optional.yml) uploads E2E logs as artifacts for audit alignment.
- **Doc preamble gate:** `python tools/harness.py doc-preamble-hygiene` is part of **Fast Required** and **governance-lane** in CI (**warn-only**; use `--enforce` locally to fail on drift).

- **Import topology commit + `pre-commit` (GOV-001):** When the **only** substantive delta is regenerating **`docs/lirix_import_topology.md`** via `python tools/gen_lirix_import_graph.py`, local `pre-commit` (notably `end-of-file-fixer`) may oscillate against the generator output so a normal commit cannot finish. In that **narrow** case, a **maintainer** may record the regenerated file with `git commit --no-verify` **only if all** of the following hold: (1) the commit message explicitly ties the change to **R-001 / import topology** (e.g. `chore(docs): regenerate lirix import topology`); (2) the **same PR** passes `python tools/gen_lirix_import_graph.py --check` and `python tools/harness.py preflight-remediation-status`; (3) the PR description or sign-off brief notes the `--no-verify` exception so reviewers do not infer a blanket hook bypass. **Do not** generalize `--no-verify` to other paths or mixed commits.
- **导入拓扑与 pre-commit（GOV-001，中文）：** 若变更实质仅为运行生成器更新 **`docs/lirix_import_topology.md`**，且本地 hook 与生成物出现往返差异导致无法普通提交，维护者可在**同一 PR** 内满足上文 (1)(2)(3) 时用 `--no-verify` **仅限该文件**；不得推广到其它路径。

## Must-have (blocking)

- [ ] **Full pytest + coverage log** under `audit_artifacts/release_signoff/<YYYY-MM-DD>/`, e.g. `B4_pytest_full_cov*.log`, with **`[tool.coverage.report].fail_under = 100`** satisfied for `lirix/`.
- [ ] **Acceptance JSON** from `tools/release_acceptance_report.py` with **`--coverage-threshold 100`** and **`--warnings-blocking`** (committed as `B4_release_acceptance_report_*.json` in the same date folder). The JSON must show `evaluation.release_ok: true`.
- [ ] **Minimum evidence set** described in the signoff README (briefs, governance log, warnings baseline log, release notes gate logs, etc.) present under that date folder.

## Recommended (non-blocking but release-grade)

- [ ] **Real Anvil E2E log** (`B4_real_e2e*.log`) **or** explicit skip documented in `B4_local_ci_equivalent_brief.md` with `E2E_SKIP_REASON=...` (see signoff README § Real E2E).
- [ ] **Performance baseline** (optional JSON): raw and/or `.normalized.json` per signoff README § Performance baseline.

## Machine-readable hints

After generating the acceptance report, open the JSON field **`recommended_artifacts_present`**: it flags whether typical E2E and perf filenames were found in the sign-off directory (inferred from the log path or `--signoff-dir`). This does **not** change `release_ok`; it is for reviewer visibility only.
