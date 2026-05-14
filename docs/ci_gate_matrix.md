---
title: CI gate matrix
purpose: 1:1 index of GitHub workflows → jobs → gates (python tools/harness.py, pytest, other)
---

# CI gate matrix

> **Spartan enforcement plane.** This file is the **1:1** contract between Markdown and `.github/workflows/*.yml`. If your change is not reflected here in the same PR, treat the merge as already red—**Fast Required** and governance lanes do not negotiate with stale narratives.

---

**EN:** 1:1 index of GitHub workflows → jobs → gates; keep in sync with `.github/workflows/*.yml` in the same PR.<br>
**中文：** 工作流、作业与门禁的一对一索引；新增 job 或 gate 时须在同 PR 内更新本文件。

### English

This file is the **1:1** index of `.github/workflows/*.yml` for Lirix. When adding a job or gate, update this table in the same PR.

### 中文

本文件为 Lirix 的 **1:1** 工作流索引；新增作业或门禁时请在同一 PR 内更新表格。文档体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## Workflow inventory (closure)

Every workflow under `.github/workflows/` is indexed below (no orphan files).

| Workflow file | Workflow `name:` (GitHub UI) | Matrix section |
| --- | --- | --- |
| `ci.yml` | CI | § `ci.yml` |
| `governance-lane.yml` | Governance Lane | § `governance-lane.yml` |
| `slow-lane-schedule.yml` | Slow Lane Schedule | § `slow-lane-schedule.yml` |
| `e2e-anvil-optional.yml` | Optional Anvil E2E | § `e2e-anvil-optional.yml` |
| `sbom-optional.yml` | Optional SBOM (CycloneDX) | § `sbom-optional.yml` |
| `mantle_fork_smoke.yml` | Mantle fork smoke | § `mantle_fork_smoke.yml` |
| `release.yml` | Release | § `release.yml` |

**Import topology artifact:** regenerate with `python tools/gen_lirix_import_graph.py`; **drift + preflight roll-up** (Fast Required / Governance, before dev install): `python tools/harness.py preflight-remediation-status` (includes the same `--check` as `import-topology`; see `docs/preflight_remediation_executor_handoff.md`).

## Shared composite

| Component | Path | Used by |
| --- | --- | --- |
| Checkout + Python + optional pip cache + optional `pip install -e ".[dev]"` | `.github/actions/lirix-ci-setup/action.yml` | `ci.yml`, `governance-lane.yml`, `slow-lane-schedule.yml`, `e2e-anvil-optional.yml`, `sbom-optional.yml`, `mantle_fork_smoke.yml` |

### Duplicate step audit

Before the composite existed, **≥4** workflows repeated the same **checkout → setup-python → pip install -e ".[dev]"`** pattern (`ci.yml` jobs `fast_required` / `coverage_required` / `pr_compat_smoke` / `compatibility_matrix`, `governance-lane.yml`, optional lanes). The composite **deduplicates** that block while preserving special cases (`fast_required` runs **hygiene** before dev install → first call uses `with-dev-install: false`; `e2e-anvil-optional` uses `checkout-repository: false` after a local checkout + Foundry; `mantle_fork_smoke` installs **after** Foundry). **`governance-lane.yml`** mirrors the same **pre-install** trio as Fast Required (`hygiene_gate` → `repo_exclusions_alignment_gate` → `python tools/harness.py preflight-remediation-status`) before `pip install -e ".[dev]"` so scheduled / `main` pushes do not silently bypass repo / topology drift gates; after dev install it also runs **`doc_preamble_hygiene_gate.py`** (warn-only, same script as `ci.yml` Fast Required) before **`cv_score_report.py`**.

**`release.yml`** intentionally **does not** use the composite: it installs **`build` + `twine`** only (no `lirix[dev]`), then publishes.

### Release workflow regression checklist

`release.yml` **does not** use `.github/actions/lirix-ci-setup` and does **not** install `.[dev]` — only `build` + `twine`. After **large changes** to the composite action, Python version pins, or packaging metadata, manually smoke the release path before publishing a tag-driven release via `push` (`v*`) or `workflow_dispatch` (existing tag input), for example:

- Local: `pip install build twine && python -m build --sdist --wheel && python -m twine check dist/*`
- Or a dry-run workflow in a fork / branch where safe.

This is intentionally separate from the mainline composite so publishing stays minimal; it also means **release is not covered** by the same `pip install -e ".[dev]"` + ruff/mypy block as `ci.yml` Fast Required.

### Local pytest defaults (`addopts`)

`pyproject.toml` appends **`tests`** (and `--pyargs lirix`) to default `addopts`, so bare `pytest path/to/one_file.py` still collects the full `tests/` tree unless you override addopts. Contributor commands and rationale: **`docs/contributing_local_tests.md`**.

### Full default collection — expected `pytest` skips (release charter)

**EN:** A bare `pytest` / full-tree run may report a **small, fixed** `skipped` count under default developer and **Fast Required** environments. That is **not** a flaky suite: those tests are **opt-in** behind env vars or live RPC fixtures.

**中文：** 默认全量 `pytest` 可能出现**少量、稳定**的 `skipped`；在默认开发与 **Fast Required** 环境下属**预期行为**，不是随机失败。

| Location | Skip condition | How to execute (opt-in) |
| --- | --- | --- |
| `tests/test_core/test_pipeline_performance_gates.py` (`test_main_paths_baseline_report`) | `os.getenv("LIRIX_RUN_PERF_BASELINE", "0") != "1"` | Set `LIRIX_RUN_PERF_BASELINE=1` (see test `skipif` / sign-off README § Performance baseline). |
| `tests/test_core/test_pipeline_performance_gates.py` (`test_main_paths_realistic_fixture_baseline_report`) | `os.getenv("LIRIX_RUN_PERF_REALISTIC_BASELINE", "0") != "1"` | Set `LIRIX_RUN_PERF_REALISTIC_BASELINE=1` (optional `LIRIX_PERF_REALISTIC_BASELINE_JSON_OUT` per test docstring). |
| `tests/test_integration/test_real_e2e_paths.py` | `pytest.skip` when `RPCUnavailableException` (no local Anvil / quorum) | Start Anvil + fixture chain (see `tests/conftest.py`, `docs/contributing_local_tests.md`, optional `.github/workflows/e2e-anvil-optional.yml`) or `RUN_ANVIL_E2E=1` where documented in `docs/release_pr_checklist.md`. |

**Merge / default CI bar:** `python tools/harness.py format-check`, `test-governance`, `test-coverage-required`, and workflow steps in **`ci.yml`** remain authoritative; **zero skip** is **not** asserted on the unconstrained full `pytest` tree unless a dedicated job (compare **Route B** in internal release engineering notes) is added and kept stable.

### Tool gates vs subprocess / runtime imports

Full index (paths, editable install, exit semantics): **`docs/tools_gates_index.md`**.

| Class | Examples | Needs `pip install -e ".[dev]"`? | Notes |
| --- | --- | --- | --- |
| **Subprocess / external CLI** | `python tools/harness.py hygiene` (`git ls-files`), `python tools/harness.py branch-protection-drift` (`gh api`, optional) | **No** (stdlib + `git` / optional `gh`) | Fails with `RuntimeError` / skip messaging when `git` or GitHub API preconditions are missing — not an editable-install problem. |
| **Imports `lirix` at runtime** | `python tools/harness.py compat-switch-expiry`, `registry-authority-contract`, `root-import-surface` | **Yes** | Import errors return exit **2** with an explicit hint to install editable dev deps (gate semantics unchanged for real failures). |

### CV automation score — semantic ceiling

`python tools/cv_score_report.py` measures **artifact / gate presence** from `docs/cv_rubric.yaml`. A **100 / 100** automated band is **not** a substitute for architecture or runtime semantics review — see **`docs/architecture_evolution_action_list.md`** (top banner) and **`docs/cv_rubric.yaml`** → `manual_review_note`.

### Docs contract gate — governance pytest SSOT

`python tools/harness.py contract-manifest` loads the **explicit** governance pytest path list from **`tools/validators.py`** (`GOVERNANCE_EXPLICIT_PYTEST_PATHS`). It also requires `.github/workflows/ci.yml` to contain the step whose stripped `- name:` line matches `GOVERNANCE_GATE_EXPLICIT_STEP_NAME`, and that step’s `run:` line must invoke **`python tools/harness.py test-governance`** (single-line harness entrypoint — no duplicate list in YAML). If you add a **second** workflow with its own governance pytest batch, extend the contract gate before treating both lists as authoritative.

It requires every `docs/audit_path_map.md` row with CI gate **Governance gate** to cite tests present in that SSOT list. A **minimal anchor** subset guards against accidental truncation of the tuple; the **exhaustive** set is **only** `GOVERNANCE_EXPLICIT_PYTEST_PATHS` (not duplicated as a second full manifest). The gate also fails if the list is **shorter than an absolute floor** (`_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS`) or is missing **anchor** paths. It checks **`docs/tools_gates_index.md`** main-table row count against the number of subcommands in **`tools/harness.py` `COMMANDS`** (the **Related tools** section is excluded).

**Gate ordering (`tools/contract_manifest_gate.py`):** the script runs **`_assert_governance_explicit_step_line_in_ci_yml`**, **`_assert_governance_step_invokes_test_harness`**, and **`_validate_tools_gates_index_row_parity`** before **`_governance_explicit_gate_tests_ssot`** / **`_validate_governance_explicit_list`**. That order fails fast on a missing or renamed governance step line, a non-harness governance `run:` line, and on malformed index table rows (the main-table row regex counts ``| `<subcommand>` |`` harness rows), instead of loading a misleading SSOT fragment first.

**Maintaining the floor:** when you add paths to `GOVERNANCE_EXPLICIT_PYTEST_PATHS`, bump `_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS` in `tools/contract_manifest_gate.py` to the new minimum count. When you introduce a new **class** of governance coverage that must never disappear from CI, add one representative path to `_GOVERNANCE_GATE_CI_YML_ANCHORS` in the same file. Run `python tools/harness.py contract-manifest` (and `pytest tests/test_tools/test_contract_manifest_gate.py`) before merging.

---

## `.github/workflows/ci.yml` — **CI**

**Triggers:** `push` to `main`, `pull_request`, `workflow_dispatch`.<br>
**Concurrency:** `ci-${{ github.workflow }}-${{ github.ref }}` (cancel in progress).

| Job (workflow `name:`) | `if:` / context | Steps / gates |
| --- | --- | --- |
| **Fast Required** | always on PR + push | `lirix-ci-setup` (Python 3.12, **no** dev install) → `python tools/harness.py hygiene` → `python tools/harness.py check-exclusions` → `python tools/harness.py preflight-remediation-status` → `pip install -e ".[dev]"` → `python tools/harness.py lint` → `python tools/harness.py format-check` → `python tools/harness.py typecheck` → **`python tools/harness.py test-governance`** (explicit list SSOT: `GOVERNANCE_EXPLICIT_PYTEST_PATHS` in `tools/validators.py`) → `python tools/harness.py registry-authority-contract` → `python tools/harness.py release-notes-gate` → `python tools/harness.py contract-manifest` → `python tools/harness.py required-check-policy` → `python tools/harness.py ci-lane-responsibility` → `python tools/harness.py compat-switch-expiry` → `python tools/harness.py plan-to-pr-exit-metrics` → `python tools/harness.py audit-internal-link` → `python tools/harness.py doc-preamble-hygiene` → `python tools/harness.py no-internal-imports` → `python tools/harness.py root-import-surface` → `python tools/harness.py test-monkeypatch-convention --strict` → `python tools/harness.py test-topology-admission` → `python tools/harness.py migration-observability-report` |
| **Coverage Required (Single Authority)** | `github.event_name != 'pull_request'`; needs `fast_required` | `lirix-ci-setup` (3.12) → **`python tools/harness.py test-coverage-required`** (`pytest -q --cov=lirix … --cov-report=xml`, **`fail_under=100`** from `pyproject.toml`) |
| **PR Compatibility Smoke (${{ matrix.os }}, py${{ matrix.python-version }})** | PR only; needs `fast_required` | `lirix-ci-setup` + pip cache → **`python tools/harness.py test-pr-compat-smoke`** |
| **Compatibility Matrix (${{ matrix.os }}, py${{ matrix.python-version }})** | non-PR; needs `fast_required` | `lirix-ci-setup` + pip cache → **`python tools/harness.py test-compat-matrix`** (`pytest -q -m "not slow and not e2e and not network and not perf and not migration"`) |

---

## `.github/workflows/governance-lane.yml` — **Governance Lane**

**Triggers:** `push` to `main`, **weekly schedule** (`cron: "0 6 * * 1"`), `workflow_dispatch`.<br>
**Concurrency:** `governance-${{ github.workflow }}-${{ github.ref }}`.

| Job | Context | Steps / gates |
| --- | --- | --- |
| **Governance Gates** | push / schedule / dispatch | `lirix-ci-setup` (3.12, **no** dev install) → `python tools/harness.py hygiene` → `python tools/harness.py check-exclusions` → `python tools/harness.py preflight-remediation-status` → `pip install -e ".[dev]"` → `python tools/harness.py doc-preamble-hygiene` → **`python tools/cv_score_report.py`** (no `--enforce`) → `python tools/harness.py branch-protection-drift` → **`python tools/harness.py ci-lane-responsibility`** → `python tools/harness.py failure-surface-triage` → `python tools/harness.py legacy-sunset` → `python tools/harness.py phase-exit-checklists` |

### Governance vs `ci.yml` overlap

| Gate | `ci.yml` | `governance-lane.yml` | Rationale |
| --- | --- | --- | --- |
| `hygiene_gate.py` + `repo_exclusions_alignment_gate.py` + `python tools/harness.py preflight-remediation-status` | Fast Required (**before** dev install) | Governance Gates (**same order**, before dev install) | **Parity:** `main` push / schedule cannot skip repo-cleanliness, exclusion SSOT, preflight roll-up (import-topology `--check` + documented worktree hazards) that PRs already hit on Fast Required. |
| `doc_preamble_hygiene_gate.py` | Fast Required (**after** `audit_internal_link_gate.py`, warn-only) | Governance Gates (**after** dev install, warn-only) | **Parity:** preamble hygiene is not skipped on `main` / schedule; governance omits `audit_internal_link_gate.py` but still runs the same warn-only script so heading drift is visible in both lanes. |
| `ci_lane_responsibility_gate.py` | Fast Required (PR + main) | Governance Gates (main + schedule) | **Keep both:** PRs must fail fast if lane docs desync; scheduled governance still catches drift if branch protection or workflow filters change. Inputs are identical; duplication is intentional redundancy across **PR** vs **scheduled** contexts. |
| `cv_score_report.py` | *(not run)* | Governance Gates | **Optional trace:** non-enforcing CV panel for `main`/schedule logs only (see `docs/cv_rubric.yaml`; PRs do not need `--enforce` until policy changes). |
| `required_check_policy_gate.py` | Fast Required | *(not run)* | **Mainline / PR only:** required GitHub checks ↔ `docs/branch_protection_required_checks.md` parity (not duplicated on governance lane). |

### PR policy: `cv_score_report.py --enforce`

**Current choice:** `cv_score_report.py` runs on **governance lane** **without** `--enforce` and is **not** on PR Fast Required.

**Rationale (keep unless team explicitly changes policy):**

- The rubric is largely **file / string existence** checks — a failing `--enforce` on every PR would churn whenever docs or optional artifacts are refactored, without always indicating a runtime regression.
- PR Fast Required already carries **high-signal** gates (`contract_manifest_gate`, governance pytest, hygiene, `preflight-remediation-status` / import-topology `--check`, etc.); adding `--enforce` duplicates **noise** vs **coverage** unless branch protection is updated to treat CV as a required check.
- **Speed:** an extra YAML parse + filesystem walk is small but non-zero on the hottest path.

If procurement or internal audit mandates a **hard numeric CV floor** on PRs, add `python tools/cv_score_report.py --enforce` to `ci.yml` **and** document the new required check in `docs/branch_protection_required_checks.md` so protection rules stay aligned.

No gate was removed from either workflow; `docs/branch_protection_required_checks.md` remains the required-check policy doc (see also `python tools/harness.py required-check-policy` in `ci.yml`).

---

## `.github/workflows/slow-lane-schedule.yml` — **Slow Lane Schedule**

**Triggers:** `workflow_dispatch`, **schedule** `cron: "0 4 * * *"`.

| Job | Steps |
| --- | --- |
| **Slow/E2E/Network/Perf** | `lirix-ci-setup` → `pytest -q -m "slow or e2e or network or perf"` |

---

## `.github/workflows/e2e-anvil-optional.yml` — **Optional Anvil E2E**

**Triggers:** `workflow_dispatch`, schedule `cron: "17 6 * * *"`.

| Job | Steps |
| --- | --- |
| **anvil-e2e** (implicit name) | `actions/checkout@v4` → `foundry-rs/foundry-toolchain@v1` (nightly) → `lirix-ci-setup` (`checkout-repository: false`) → start `anvil` → `pytest … tests/test_integration/test_real_e2e_paths.py` → upload log artifact |

---

## `.github/workflows/sbom-optional.yml` — **Optional SBOM (CycloneDX)**

**Triggers:** `workflow_dispatch` only.

| Job | Steps |
| --- | --- |
| **sbom** | `lirix-ci-setup` → `pip install cyclonedx-bom` → `cyclonedx-py environment -o lirix-sbom.json` → upload SBOM artifact |

---

## `.github/workflows/mantle_fork_smoke.yml` — **Mantle fork smoke**

**Triggers:** `workflow_dispatch` only.

| Job | Steps |
| --- | --- |
| **Mantle fork (Anvil + mantle_TT)** | `lirix-ci-setup` (no dev install) → Foundry toolchain → `pip install -e ".[dev]"` → conditional `pytest mantle_TT/tests/mantle/` when `MANTLE_MAINNET_RPC` secret is set |

---

## `.github/workflows/release.yml` — **Release**

**Triggers:** `push` of tags matching `v*` and `workflow_dispatch` with an explicit existing tag input. This workflow is **not** driven by a GitHub Release `published` event. It runs from the tag / dispatch entrypoint, checks out **`${{ github.event_name == 'workflow_dispatch' && github.event.inputs.tag || github.sha }}`**, builds **sdist + wheel**, runs **`twine check`**, publishes to **PyPI** (OIDC), then **attaches `dist/*`** to the matching GitHub Release via `softprops/action-gh-release`.

| Job | Steps |
| --- | --- |
| **build** | `actions/checkout@v4` (ref = tag or dispatch input) → `setup-python` + pip cache → `pip install build twine` → `python -m build --sdist --wheel` → `twine check` → upload `dist/` artifact |
| **publish** | download `dist/` artifact → PyPI publish action → attach `dist/*` to the release identified by `RELEASE_TAG` |

### Release workflow truth table

- **Tag push** (`v*`): builds and publishes the tagged release.
- **Workflow dispatch**: republishes an existing tag after a fix or re-run.
- **GitHub Release UI/API publish event**: not a trigger for this workflow.

**Rule:** trigger facts take precedence over narrative shorthand; if these bullets and the YAML diverge, update this section to match the workflow file in the same PR.

### Optional SBOM / Anvil E2E — procurement and release sign-off (manual)

These workflows are **optional** and **not** wired to external CD/SaaS. For **vendor / security procurement** or **release governance**, treat them as **evidence artifacts** you attach to the human checklist (no automated KPI substitute):

1. **SBOM (`sbom-optional.yml`):** In GitHub → **Actions** → **Optional SBOM (CycloneDX)** → **Run workflow** on the commit you are reviewing. Download **`lirix-sbom.json`** from the run summary. Store it with the ticket or release record; on upgrades, diff against the prior SBOM or run your org’s CycloneDX policy tooling locally.
2. **Anvil E2E (`e2e-anvil-optional.yml`):** Run on demand or rely on the scheduled run; download uploaded **logs / artifacts** if the job records them. Use the outcome as **supplementary** chain-adjacent signal — mainline correctness remains **`ci.yml`** Fast Required + coverage policy.
3. **Release publish:** Before publishing a GitHub **Release** for a version tag, confirm `release.yml` expectations still match **`§ Release workflow regression checklist`** above; optional-lane artifacts do **not** block `release.yml` unless you explicitly add branch protection checks for those workflows.

This closes the **manual gap** called out in `docs/cv_rubric.yaml` → dimension **`security_sto`** (optional workflows indexed here; **consumption** is process, not SaaS).

---

## PR / main / scheduled quick index

| Context | Workflows typically running required / heavy lanes |
| --- | --- |
| **Pull request** | `ci.yml` → **Fast Required**, **PR Compatibility Smoke** |
| **Push to `main`** | `ci.yml` → Fast + Coverage + Compatibility; `governance-lane.yml` → Governance Gates |
| **Scheduled** | `governance-lane.yml`, `slow-lane-schedule.yml`, `e2e-anvil-optional.yml` (per each file’s `cron`) |
