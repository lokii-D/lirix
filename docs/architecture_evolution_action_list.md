---
title: Architecture evolution action list
purpose: post-harness plan items — path/gate, action, benefit, acceptance
---

# Architecture evolution action list


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

**CV automated score (post-todos, `python3 tools/cv_score_report.py`):** **100 / 100** — target band **≥95** met as of **2026-05-11** (automated checks from `docs/cv_rubric.yaml` only).

**Rubric structure / version discipline:** **`docs/cv_rubric.yaml`** `version` was bumped when **`ci_alignment`** automated sub-scores were re-weighted (external caches should treat rubric **v2** as a distinct artifact from **v1**).

**Semantic ceiling (do not misread the number):** automated **100 / 100** means **artifacts and gates exist** (existence band). It does **not** mean semantic architecture audit, threat modelling, or runtime behaviour sign-off is complete — see `manual_review_note` in **`docs/cv_rubric.yaml`**, **`docs/ci_gate_matrix.md`** (§ CV automation score), and the README audit entrypoint list.

**Post-`r5-*` (unchanged):** stronger **CV automation** and **contract gate** checks still **do not** replace threat modelling or human architecture review — same boundary as `manual_review_note` in **`docs/cv_rubric.yaml`** (cross-check that section when editing this banner).

**Prior plan baseline (human narrative in architecture plan):** **85 / 100** — gap was mostly documentation, CI index, and CV metering artifacts. The rows below record how each assigned todo closed that gap without changing runtime semver contracts.

## Assigned todo closure (IDs)

| Todo ID | Outcome | Evidence |
| --- | --- | --- |
| `audit-map-registry-row` | Done | `docs/audit_path_map.md` — separate rows for `lirix/registry/__init__.py` vs `bridges.py` |
| `audit-map-intents-row` | Done | same — `intents/__init__.py` vs `translator.py`; directory closure explicit |
| `audit-map-audit-row` | Done | same — `audit/__init__.py` vs `logger.py` + hook test cross-refs |
| `ci-gate-matrix-doc` | Done | `docs/ci_gate_matrix.md` + workflow inventory table |
| `ci-duplicate-step-audit` | Done | matrix § Duplicate step audit + `.github/actions/lirix-ci-setup/action.yml` |
| `optional-workflow-headers` | Done | YAML comment headers on optional / scheduled workflows (see matrix) |
| `governance-vs-ci-overlap` | Done | matrix § Governance vs `ci.yml` overlap + `docs/branch_protection_required_checks.md` |
| `cv-rubric-yaml` | Done | `docs/cv_rubric.yaml` — weights = 100, scoring_rules + veto_if + gates |
| `cv-score-script` | Done | `tools/cv_score_report.py` — `--enforce`, veto parsing (`missing_path`) |
| `cv-wire-ci-optional` | Done | `.github/workflows/governance-lane.yml` runs `python tools/cv_score_report.py` (no `--enforce`) |
| `legacy-surface-inventory` | Done | `docs/migration_legacy_to_v2.md` § Legacy surface inventory + audit map scope |
| `cli-exports-consistency` | Done | `tests/test_core/test_cli_public_contract.py` — README + frozen subcommands |
| `action-list-doc` | Done | this file |
| `score-recalc-after-todos` | Done | automated band **100 / 100** (≥95); date **2026-05-11** |
| `harness-definition-doc` | merged-into-row | **Harness 口径**写入 `docs/audit_path_map.md` § Harness alignment；计划正文不重复 |
| `exclusions-ssot` | merged-into-row | `docs/repo_exclusions.md` + `.harnessignore` + 审计 Scope 段；**r2** 见 `tools/repo_exclusions_alignment_gate.py` |
| `gitignore-venv312` | merged-into-row | `.gitignore` 中 `.venv*/` 与虚拟环境 glob；与 `repo_exclusions` / hygiene 叙述一致 |
| `dep-graph-artifact` | merged-into-row | `docs/lirix_import_topology.md` + `tools/gen_lirix_import_graph.py`；**r2** drift：`gen_lirix_import_graph.py --check`（`ci.yml` Fast Required） |
| `evidence-flow-mini` | merged-into-row | `docs/pipeline_evidence_flow.md` + audit / matrix 引用 |

**Closure 计数说明：**上表含首轮计划 **19/19** todo id（含 5 条 `merged-into-row` 与证据路径）；第 2 轮 **11** 条 `r2-*` 见 **Round 2**；第 3 轮 **10** 条 `r3-*` 见 **Round 3**；第 4 轮 **9** 条 `r4-*` 见 **Round 4**；第 5 轮 **8** 条 `r5-*` 见 **Round 5**（`r1` + `r2` + `r3` + `r4` + `r5` 分层可追溯）。

## Round 2 todo closure (`r2-*`)

| Todo ID | Outcome | Evidence |
| --- | --- | --- |
| `r2-pytest-addopts-contributor-doc` | Done | `docs/contributing_local_tests.md`（`addopts` / `pytest -o addopts=` / `PYTEST_ADDOPTS=` / `pip install -e`）；README 审计链 grep |
| `r2-subprocess-gates-venv-doc` | Done | `docs/ci_gate_matrix.md` § Tool gates vs subprocess；`hygiene_gate.py` / `branch_protection_drift_gate.py` docstring；`compat_switch_expiry_gate.py` / `registry_authority_contract_gate.py` / `root_import_surface_gate.py` ImportError→exit 2 |
| `r2-import-topology-drift-gate` | Done | `tools/gen_lirix_import_graph.py`（`format_topology_markdown`、`--check`）；`.github/workflows/ci.yml` Fast Required 在 dev install 前调用 `python tools/harness.py preflight-remediation-status`（内含 `--check`）；治理车道同序 |
| `r2-contract-manifest-dual-source` | Done | `tools/contract_manifest_gate.py` — `_GOVERNANCE_GATE_CI_YML_ANCHORS` 与注释（完整列表仅以 `ci.yml` 为准）；audit Governance 行 ⊆ 解析列表循环校验 |
| `r2-cv-automation-ceiling-doc` | Done | 本文件顶栏 Semantic ceiling；`docs/cv_rubric.yaml` `manual_review_note`；`docs/ci_gate_matrix.md` § CV automation score；README 审计链 |
| `r2-action-list-todo-id-parity` | Done | 本文件首轮 closure 表 **19/19** 与 `merged-into-row` 说明 |
| `r2-empty-decoder-policy-product-decision` | Done | `docs/audit_path_map.md` § ADR-lite empty resolved decoder plugins |
| `r2-exclusions-cross-file-gate` | Done | `tools/repo_exclusions_alignment_gate.py`；`ci.yml` hygiene 后调用 |
| `r2-cv-score-pyyaml-ux` | Done | `tools/cv_score_report.py` — `yaml` import 前 try/except，stderr 提示 `pip install -e` / pyyaml，return 2 |
| `r2-release-workflow-regression-note` | Done | `docs/ci_gate_matrix.md` § Release workflow regression checklist |
| `r2-pr-cv-enforce-policy` | Done | `docs/ci_gate_matrix.md` § PR policy: `cv_score_report --enforce` |

## Round 3 todo closure (`r3-*`)

| Todo ID | Outcome | Evidence |
| --- | --- | --- |
| `r3-action-list-r2-closure-table` | Done | 本文件 **Round 2 todo closure** 表 **11** 行 + 上文 closure 计数指向下表 |
| `r3-governance-lane-fast-parity` | Done | `.github/workflows/governance-lane.yml`（`with-dev-install: false`、hygiene → exclusions → `gen_lirix_import_graph.py --check` → `pip install -e`）；`docs/ci_gate_matrix.md` Governance 行与 § overlap **Parity** |
| `r3-repo-exclusions-gate-harden` | Done | `tools/repo_exclusions_alignment_gate.py` — `_path_or_doc_token` 与 `audit_path_map.md` Scope / Exclusions 交叉校验 |
| `r3-contract-manifest-extractor-guard` | Done | `tools/contract_manifest_gate.py` — `_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS`、锚点；`tests/test_tools/test_contract_manifest_gate.py`（真实 `ci.yml` 解析等） |
| `r3-cv-rubric-contributing-path` | Done | `docs/cv_rubric.yaml` `contributing_local_tests_doc`；`tools/cv_score_report.py` 模块 docstring |
| `r3-tools-gates-index` | Done | `docs/tools_gates_index.md`；`docs/ci_gate_matrix.md` § Tool gates 链到索引 |
| `r3-readme-zh-audit-parity` | Done | `README.md` 中文「审计与本地校验入口」与英文 Audit 链同族文档 |
| `r3-sbom-e2e-procurement-narrative` | Done | `docs/ci_gate_matrix.md` § Optional SBOM / Anvil E2E；`docs/release_notes.md` Unreleased；`docs/cv_rubric.yaml` `security_sto` / `manual_review_note` |
| `r3-lirix-importerror-sweep` | Done | `tools/` 内 `from lirix` / `import lirix` 仅兼容门闸三处 + `registry_authority_contract_gate.py` 单 try |
| `r3-pipeline-evidence-optional-checklist` | Done | `docs/pipeline_evidence_flow.md` 顶部 **Maintainer checklist** |

## Round 4 todo closure (`r4-*`)

| Todo ID | Outcome | Evidence |
| --- | --- | --- |
| `r4-action-list-r3-closure-table` | Done | 本文件 **Round 3 todo closure** 表 **10** 行 + 上文 closure 计数指向下表 |
| `r4-contract-manifest-governance-step-constant` | Done | `tools/contract_manifest_gate.py` — `GOVERNANCE_GATE_EXPLICIT_STEP_NAME`；`contract-manifest` 绑定 `ci.yml` harness 步骤 + `tools/validators.py` SSOT |
| `r4-contract-manifest-floor-unit-integration` | Done | `_validate_governance_explicit_list`；`tests/test_tools/test_contract_manifest_gate.py`（floor / 空列表 / 锚点等） |
| `r4-readme-tools-gates-index-crosslink` | Done | `README.md` 英 / 中文审计链一带 `docs/tools_gates_index.md` 与矩阵 § 互补说明 |
| `r4-cv-rubric-tools-index-metering` | Done | `docs/cv_rubric.yaml` `ci_alignment` 子项（含 `tools_gates_index_doc`）；`tools/cv_score_report.py` 模块说明 |
| `r4-branch-protection-governance-job-narrative` | Done | `docs/branch_protection_required_checks.md` § **Required status checks: job names vs steps** |
| `r4-governance-min-tests-bump-policy` | Done | `contract_manifest_gate.py` 注释 + `docs/ci_gate_matrix.md` § **Maintaining the floor** |
| `r4-release-notes-procurement-zh` | Done | `docs/release_notes.md` Unreleased 中英文并列 SBOM/E2E 采购句 |
| `r4-compat-switch-import-consolidation-optional` | Done | `tools/compat_switch_expiry_gate.py` — `main` 单 try `from lirix`，`lirix_imports` dict 传入断言 |

## Round 5 todo closure (`r5-*`)

| Todo ID | Outcome | Evidence |
| --- | --- | --- |
| `r5-action-list-r4-closure-table` | Done | 本文件 **Round 4 todo closure** 表 **9** 行 + 上文 closure 计数指向下表 |
| `r5-cv-rubric-version-discipline` | Done | `docs/cv_rubric.yaml` `version: 2`；本文件顶栏 **Rubric structure / version discipline**；`docs/release_notes.md` Unreleased **CV rubric v2** |
| `r5-contract-manifest-step-vs-ci-yml-sync` | Done | `tools/contract_manifest_gate.py` — `_assert_governance_explicit_step_line_in_ci_yml`；`main` 在解析列表前调用；失败文案指向矩阵 § Docs contract gate |
| `r5-contributing-pytest-override-ini` | Done | `docs/contributing_local_tests.md` — `--override-ini='addopts='` 与 `-o addopts=` 并列 |
| `r5-tools-gates-index-row-count-check` | Done | `_validate_tools_gates_index_row_parity` + `_TOOLS_GATES_INDEX_MAIN_ROW_RE`；`docs/tools_gates_index.md` **Row parity**；矩阵 § Docs contract gate |
| `r5-required-check-policy-crossref` | Done | `tools/required_check_policy_gate.py` docstring + 读 `governance-lane.yml` 断言 **Governance Gates** job；`docs/branch_protection_required_checks.md` **Cross-check** |
| `r5-audit-path-map-contributor-tools-link` | Done | `docs/audit_path_map.md` contributor bullet → `docs/tools_gates_index.md` |
| `r5-extractor-single-workflow-assumption-doc` | Done | 治理 pytest 路径 SSOT 在 **`tools/validators.py`**；`docs/ci_gate_matrix.md` § Docs contract gate |

## Action rows (path or gate)

| Path / gate | Action | Benefit | Acceptance |
| --- | --- | --- | --- |
| `docs/audit_path_map.md` | **merge** (additive rows) Harness terminology + per-file subtree mapping | single audit vocabulary; no dangling subtrees | every `lirix/registry|intents|audit` file has a table row or explicit bridge note |
| `docs/repo_exclusions.md` + `.harnessignore` | **merge** SSOT exclusions | `.gitignore` / pytest / audit / harness aligned | four-way table + glob mirror |
| `.github/workflows/*` + `.github/actions/lirix-ci-setup` | **merge** composite + matrix | less YAML drift; faster audits | `docs/ci_gate_matrix.md` 1:1 + composite path exists |
| `docs/ci_gate_matrix.md` | **decouple** narrative from workflow YAML | explains intentional duplicate `ci_lane_responsibility_gate` | PR vs schedule rationale written |
| `docs/cv_rubric.yaml` + `tools/cv_score_report.py` | **refactor** (iterate) rubric + script | measurable CV band | governance lane logs score; `--enforce` optional |
| `docs/pipeline_evidence_flow.md` | **merge** orchestrator-order evidence narrative | audit joins predictable | Mermaid aligns with `LirixPipelineOrchestrator` stages |
| `docs/lirix_import_topology.md` | **merge** generated import edges | architecture artifact | `gen_lirix_import_graph.py` + doc committed |
| `tests/test_core/test_cli_public_contract.py` | **merge** CLI + README contract | README `lirix init` cannot drift silently | governance pytest includes file |
| `lirix/shield`, `lirix/legacy`, `lirix/core/guard` | **decouple** (document-only) inventory | semver-safe surface clarity | `docs/migration_legacy_to_v2.md` § inventory + audit map pointer |
| Optional workflows (`*optional*.yml`, `slow-lane-schedule.yml`, `mantle_fork_smoke.yml`) | **merge** YAML header comments | STO/e2e/perf intent visible at file top | headers reference `docs/ci_gate_matrix.md` |

## Prior gap → closure (plan score narrative)

| Former gap (plan) | Closure |
| --- | --- |
| CV artifacts missing | `cv_rubric.yaml`, `cv_score_report.py`, topology generator, action list |
| CI narrative scattered | `ci_gate_matrix.md` + optional workflow headers |
| Exclusions not SSOT | `repo_exclusions.md` + `.harnessignore` |
| Harness term undefined | Harness alignment section in `audit_path_map.md` |
| Plan score **85** (human rubric) | Automated metering band **100 / 100** when artifacts present; human architecture score still reviewed outside CI |
