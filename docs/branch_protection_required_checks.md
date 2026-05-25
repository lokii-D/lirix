# Branch Protection Required Checks

> **Cold path only.** Required check names mirror workflow **job** `name:` strings, not step labels. Drift between this document and `.github/workflows/*.yml` is a defect with a ticket number, not a hallway conversation.

---

**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This repository keeps PR quality gates regression-safe while preserving a separate
slow/non-PR compatibility lane.

## Required on Pull Requests

- `Fast Required` (from `.github/workflows/ci.yml`)
- `PR Compatibility Smoke (...)` (from `.github/workflows/ci.yml`)

## Strategy (why A+)

This repository uses an **A+ fast/slow split**:

- PRs get fast deterministic feedback (contracts + hygiene + smoke matrix).
- `main` remains **fail-closed** on the full suite and `fail_under=100` coverage.

## Non-PR Slow Lane

- `Coverage Required (Single Authority)` (runs on `push/main`, `workflow_dispatch`)
- `Compatibility Matrix (...)` (runs on `push/main` when not a PR, `workflow_dispatch`)
- `Governance Gates` (from `.github/workflows/governance-lane.yml`)
- optional workflows:
  - `.github/workflows/e2e-anvil-optional.yml`
  - `.github/workflows/mantle_fork_smoke.yml`
  - `.github/workflows/mantle-harness-ci.yml`
  - `.github/workflows/sbom-optional.yml`
  - `.github/workflows/slow-lane-schedule.yml`

## Governance Rule

The branch-protection required checks MUST include:

- `Fast Required`
- `PR Compatibility Smoke (...)`

The full `Compatibility Matrix (...)` and `Coverage Required (Single Authority)` remain non-PR lanes
so contributors get fast feedback on PRs while main remains fail-closed on coverage.

## Required status checks: job names vs steps (GitHub Actions)

Branch protection rules match **check run names** emitted for each **job**, not the titles of individual **steps** inside a job. Configure required checks using the job’s display `name:` from the workflow (for example **`Fast Required`** and **`PR Compatibility Smoke (...)`** from `.github/workflows/ci.yml`, and **`Governance Gates`** from `.github/workflows/governance-lane.yml` on job `governance_gates`). Step labels such as `Hygiene gate (...)` or **`Governance gate (explicit)`** (the pytest list step inside Fast Required) are **not** separate selectable checks in GitHub’s branch protection UI unless you add another job or a publisher that registers them. This matches **`docs/ci_gate_matrix.md`** § **Governance vs `ci.yml` overlap** (parity is about **which gates run** in each lane, not about duplicating every step as a required check).

**Cross-check:** `tools/required_check_policy_gate.py` asserts that the backticked PR required checks in § **Required on Pull Requests** / § **Governance Rule** resolve to real **`name:`** values in `.github/workflows/ci.yml`, and that **`Governance Gates`** appears as a job `name:` in `.github/workflows/governance-lane.yml` and is mentioned in this doc (examples stay aligned with `parse_workflow_job_names` / `doc_check_satisfied` in `tools/ci_gate_shared.py`).

## Automated Drift Detection

- `tools/branch_protection_drift_gate.py` validates docs vs workflow and (when available) live GitHub branch protection.
- `tools/ci_lane_responsibility_gate.py` enforces fast-required vs non-PR heavy-lane boundaries.
