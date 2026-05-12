---
title: CI gate matrix
purpose: 1:1 index of GitHub workflows → jobs → gates (python tools/harness.py, pytest, other)
---

# CI gate matrix

> **Spartan enforcement plane.** This file is the **1:1** contract between Markdown and `.github/workflows/*.yml`. If your change is not reflected here in the same PR, treat the merge as already red—**Fast Required** and governance lanes do not negotiate with stale narratives.

---

**EN:** 1:1 index of GitHub workflows → jobs → gates; keep in sync with `.github/workflows/*.yml` in the same PR.  
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

**Import topology artifact:** regenerate with `python tools/gen_lirix_import_graph.py`; **drift gate** (Fast Required, before dev install): `python tools/gen_lirix_import_graph.py --check`.

## Shared composite

| Component | Path | Used by |
| --- | --- | --- |
| Checkout + Python + optional pip cache + optional `pip install -e ".[dev]"` | `.github/actions/lirix-ci-setup/action.yml` | `ci.yml`, `governance-lane.yml`, `slow-lane-schedule.yml`, `e2e-anvil-optional.yml`, `sbom-optional.yml`, `mantle_fork_smoke.yml` |

### Duplicate step audit

Before the composite existed, **≥4** workflows repeated the same **checkout → setup-python → pip install -e ".[dev]"`** pattern (`ci.yml` jobs `fast_required` / `coverage_required` / `pr_compat_smoke` / `compatibility_matrix`, `governance-lane.yml`, optional lanes). The composite **deduplicates** that block while preserving special cases (`fast_required` runs **hygiene** before dev install → first call uses `with-dev-install: false`; `e2e-anvil-optional` uses `checkout-repository: false` after a local checkout + Foundry; `mantle_fork_smoke` installs **after** Foundry). **`governance-lane.yml`** mirrors the same **pre-install** trio as Fast Required (`hygiene_gate` → `repo_exclusions_alignment_gate` → `gen_lirix_import_graph.py --check`) before `pip install -e ".[dev]"` so scheduled / `main` pushes do not silently bypass repo / topology drift gates; after dev install it also runs **`doc_preamble_hygiene_gate.py`** (warn-only, same script as `ci.yml` Fast Required) before **`cv_score_report.py`**.

**`release.yml`** intentionally **does not** use the composite: it installs **`build` + `twine`** only (no `lirix[dev]`), then publishes.

### Release workflow regression checklist

`release.yml` **does not** use `.github/actions/lirix-ci-setup` and does **not** install `.[dev]` — only `build` + `twine`. After **large changes** to the composite action, Python version pins, or packaging metadata, manually smoke the release path before **publishing a GitHub Release** (the workflow runs on `release: published` only), for example:

- Local: `pip install build twine && python -m build --sdist --wheel && python -m twine check dist/*`
- Or a dry-run workflow in a fork / branch where safe.

This is intentionally separate from the mainline composite so publishing stays minimal; it also means **release is not covered** by the same `pip install -e ".[dev]"` + ruff/mypy block as `ci.yml` Fast Required.

### Local pytest defaults (`addopts`)

`pyproject.toml` appends **`tests`** (and `--pyargs lirix`) to default `addopts`, so bare `pytest path/to/one_file.py` still collects the full `tests/` tree unless you override addopts. Contributor commands and rationale: **`docs/contributing_local_tests.md`**.

### Tool gates vs subprocess / runtime imports

Full index (paths, editable install, exit semantics): **`docs/tools_gates_index.md`**.

| Class | Examples | Needs `pip install -e ".[dev]"`? | Notes |
| --- | --- | --- | --- |
| **Subprocess / external CLI** | `python tools/harness.py hygiene` (`git ls-files`), `python tools/harness.py branch-protection-drift` (`gh api`, optional) | **No** (stdlib + `git` / optional `gh`) | Fails with `RuntimeError` / skip messaging when `git` or GitHub API preconditions are missing — not an editable-install problem. |
| **Imports `lirix` at runtime** | `python tools/harness.py compat-switch-expiry`, `registry-authority-contract`, `root-import-surface` | **Yes** | Import errors return exit **2** with an explicit hint to install editable dev deps (gate semantics unchanged for real failures). |

### CV automation score — semantic ceiling

`python tools/cv_score_report.py` measures **artifact / gate presence** from `docs/cv_rubric.yaml`. A **100 / 100** automated band is **not** a substitute for architecture or runtime semantics review — see **`docs/architecture_evolution_action_list.md`** (top banner) and **`docs/cv_rubric.yaml`** → `manual_review_note`.

### Docs contract gate — governance pytest SSOT

`python tools/harness.py contract-manifest` parses the **explicit** governance pytest list from **only** `.github/workflows/ci.yml` (not `governance-lane.yml`): the step whose stripped `- name:` line matches `GOVERNANCE_GATE_EXPLICIT_STEP_NAME` in that script. If you add a **second** workflow with its own duplicate explicit pytest list, update the extractor or add a manifest before treating both lists as authoritative. The gate also asserts that exact `- name:` line exists in `ci.yml` so the constant cannot drift from YAML alone.

It requires every `docs/audit_path_map.md` row with CI gate **Governance gate** to cite tests present in that extracted list. A **minimal anchor** subset inside the gate only guards against accidental truncation of the YAML list; the **exhaustive** set is **only** the `ci.yml` step (not duplicated as a second full manifest). The gate also fails if the extracted list is **shorter than an absolute floor** (`_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS`) or is missing **anchor** paths (so renaming that step cannot yield an empty list that still passes). It checks **`docs/tools_gates_index.md`** main-table row count against the number of subcommands in **`tools/harness.py` `COMMANDS`** (the **Related tools** section is excluded).

**Gate ordering (`tools/contract_manifest_gate.py`):** the script runs **`_assert_governance_explicit_step_line_in_ci_yml`** and **`_validate_tools_gates_index_row_parity`** *before* **`_extract_governance_gate_tests`** / **`_validate_governance_explicit_list`**. That order fails fast on a missing or renamed governance step line and on malformed index table rows (the main-table row regex counts ``| `<subcommand>` |`` harness rows), instead of parsing a potentially misleading fragment of `ci.yml` first. Cheap structural checks therefore precede the heavier governance list extraction.

**Maintaining the floor:** when you add `tests/...py` lines to the explicit governance step in `ci.yml`, bump `_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS` in `tools/contract_manifest_gate.py` to the new minimum count. When you introduce a new **class** of governance coverage that must never disappear from CI, add one representative path to `_GOVERNANCE_GATE_CI_YML_ANCHORS` in the same file. Run `python tools/harness.py contract-manifest` (and `pytest tests/test_tools/test_contract_manifest_gate.py`) before merging.

---

## `.github/workflows/ci.yml` — **CI**

**Triggers:** `push` to `main`, `pull_request`, `workflow_dispatch`.  
**Concurrency:** `ci-${{ github.workflow }}-${{ github.ref }}` (cancel in progress).

| Job (workflow `name:`) | `if:` / context | Steps / gates |
| --- | --- | --- |
| **Fast Required** | always on PR + push | `lirix-ci-setup` (Python 3.12, **no** dev install) → `python tools/harness.py hygiene` → `python tools/harness.py check-exclusions` → `python tools/gen_lirix_import_graph.py --check` → `pip install -e ".[dev]"` → `ruff check .` → `black --check .` → `mypy --strict lirix` → **Governance pytest** (explicit multi-file list in `ci.yml`: session/replay/hook/config closure + exports/CLI/readme + layers L4/L5 + LangChain delegate) → `python tools/harness.py registry-authority-contract` → release notes `rg` checks → `python tools/harness.py contract-manifest` → `python tools/harness.py required-check-policy` → `python tools/harness.py ci-lane-responsibility` → `python tools/harness.py compat-switch-expiry` → `python tools/harness.py plan-to-pr-exit-metrics` → `python tools/harness.py audit-internal-link` → `python tools/harness.py doc-preamble-hygiene` → `python tools/harness.py no-internal-imports` → `python tools/harness.py root-import-surface` → `python tools/harness.py test-monkeypatch-convention --strict` → `python tools/harness.py test-topology-admission` → `python tools/migration_observability_report.py` |
| **Coverage Required (Single Authority)** | `github.event_name != 'pull_request'`; needs `fast_required` | `lirix-ci-setup` (3.12) → `pytest -q --cov=lirix … --cov-report=xml` (**`fail_under=100`** from `pyproject.toml`) |
| **PR Compatibility Smoke (${{ matrix.os }}, py${{ matrix.python-version }})** | PR only; needs `fast_required` | `lirix-ci-setup` + pip cache → `pytest -q` on `test_entrypoints.py`, `test_sync_async_contract_consistency.py`, `test_registry_authority_contract.py` |
| **Compatibility Matrix (${{ matrix.os }}, py${{ matrix.python-version }})** | non-PR; needs `fast_required` | `lirix-ci-setup` + pip cache → `pytest -q -m "not slow and not e2e and not network and not perf and not migration"` |

---

## `.github/workflows/governance-lane.yml` — **Governance Lane**

**Triggers:** `push` to `main`, **weekly schedule** (`cron: "0 6 * * 1"`), `workflow_dispatch`.  
**Concurrency:** `governance-${{ github.workflow }}-${{ github.ref }}`.

| Job | Context | Steps / gates |
| --- | --- | --- |
| **Governance Gates** | push / schedule / dispatch | `lirix-ci-setup` (3.12, **no** dev install) → `python tools/harness.py hygiene` → `python tools/harness.py check-exclusions` → `python tools/gen_lirix_import_graph.py --check` → `pip install -e ".[dev]"` → `python tools/harness.py doc-preamble-hygiene` → **`python tools/cv_score_report.py`** (no `--enforce`) → `python tools/harness.py branch-protection-drift` → **`python tools/harness.py ci-lane-responsibility`** → `python tools/harness.py failure-surface-triage` → `python tools/harness.py legacy-sunset` → `python tools/harness.py phase-exit-checklists` |

### Governance vs `ci.yml` overlap

| Gate | `ci.yml` | `governance-lane.yml` | Rationale |
| --- | --- | --- | --- |
| `hygiene_gate.py` + `repo_exclusions_alignment_gate.py` + `gen_lirix_import_graph.py --check` | Fast Required (**before** dev install) | Governance Gates (**same order**, before dev install) | **Parity:** `main` push / schedule cannot skip repo-cleanliness, exclusion SSOT, or committed import-topology drift checks that PRs already hit on Fast Required. |
| `doc_preamble_hygiene_gate.py` | Fast Required (**after** `audit_internal_link_gate.py`, warn-only) | Governance Gates (**after** dev install, warn-only) | **Parity:** preamble hygiene is not skipped on `main` / schedule; governance omits `audit_internal_link_gate.py` but still runs the same warn-only script so heading drift is visible in both lanes. |
| `ci_lane_responsibility_gate.py` | Fast Required (PR + main) | Governance Gates (main + schedule) | **Keep both:** PRs must fail fast if lane docs desync; scheduled governance still catches drift if branch protection or workflow filters change. Inputs are identical; duplication is intentional redundancy across **PR** vs **scheduled** contexts. |
| `cv_score_report.py` | *(not run)* | Governance Gates | **Optional trace:** non-enforcing CV panel for `main`/schedule logs only (see `docs/cv_rubric.yaml`; PRs do not need `--enforce` until policy changes). |
| `required_check_policy_gate.py` | Fast Required | *(not run)* | **Mainline / PR only:** required GitHub checks ↔ `docs/branch_protection_required_checks.md` parity (not duplicated on governance lane). |

### PR policy: `cv_score_report.py --enforce`

**Current choice:** `cv_score_report.py` runs on **governance lane** **without** `--enforce` and is **not** on PR Fast Required.

**Rationale (keep unless team explicitly changes policy):**

- The rubric is largely **file / string existence** checks — a failing `--enforce` on every PR would churn whenever docs or optional artifacts are refactored, without always indicating a runtime regression.
- PR Fast Required already carries **high-signal** gates (`contract_manifest_gate`, governance pytest, hygiene, import-topology `--check`, etc.); adding `--enforce` duplicates **noise** vs **coverage** unless branch protection is updated to treat CV as a required check.
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

**Triggers:** `release` **published** only (not `push` to `main`, not bare tag push). After you publish a GitHub Release from the UI (or API), this job checks out **`${{ github.event.release.tag_name }}`**, builds **sdist + wheel**, runs **`twine check`**, publishes to **PyPI** (OIDC), then **attaches `dist/*`** to that same Release via `softprops/action-gh-release` (does **not** regenerate release notes, so the description you entered stays intact).

| Job | Steps |
| --- | --- |
| **publish** | `actions/checkout@v4` (ref = release tag) → `setup-python` + pip cache → `pip install build twine` → `python -m build --sdist --wheel` → `twine check` → PyPI publish action → attach `dist/*` to the existing GitHub Release |

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
