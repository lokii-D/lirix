# Local CI-equivalent brief (sign-off)

**EN:** Template for the B4 brief — copy into a dated folder and fill placeholders; pairs with [`README.md`](README.md) in this directory.
**中文：** B4 简报模板；复制到 `audit_artifacts/release_signoff/<YYYY-MM-DD>/B4_local_ci_equivalent_brief.md` 后替换占位符。说明见同目录 [`README.md`](README.md)。体例见 [`docs/documentation_styleguide.md`](../../docs/documentation_styleguide.md)。

### English

Copy this file to `audit_artifacts/release_signoff/<YYYY-MM-DD>/B4_local_ci_equivalent_brief.md` and replace placeholders.

### 中文

将本文件复制到日期子目录并重命名为 `B4_local_ci_equivalent_brief.md`，填写占位内容。

## Commands run

- Full verification: run the CI-equivalent step list in this directory’s [`README.md`](README.md) § **How to generate** (or paste equivalent per-step logs referenced below).
- Python: `(paste python --version)`.
- Virtualenv / toolchain notes: `(optional)`.

## Evidence pointers

- Ruff / Black / MyPy logs: `(filenames under this date folder)`.
- Governance explicit pytest log: `(e.g. B4_governance_gate_explicit_pytest*.log)`.
- Full pytest + coverage log: `(e.g. B4_pytest_full_cov*.log)`.
- Acceptance JSON: `(e.g. B4_release_acceptance_report*.json)` — must show `evaluation.release_ok: true` with `--warnings-blocking`.

## Real E2E (Anvil)

Either attach `B4_real_e2e*.log` from a successful run, or document a skip:

`E2E_SKIP_REASON=(no Foundry on maintainer machine | CI-only bundle | other — one line)`
