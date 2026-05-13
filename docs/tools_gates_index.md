---
title: Tools gates index
purpose: quick reference for `tools/harness.py` policy gates — deps, exit codes, doc links
---

# Tools gates index

> **SSOT — policy engine surface.** This matrix is Lirix’s canonical map of **`python tools/harness.py`** subcommands. CI treats any attempt to bypass the harness entrypoint as a merge-time hard failure—there is no shadow operator lane.

---

**EN:** All gates are consolidated into a single entrypoint: **`python tools/harness.py <subcommand>`**.
All gate logic now lives in **`tools/validators.py`** as native Python functions; the original 18 standalone gate scripts are fully retired.

### English

Companion to **`docs/ci_gate_matrix.md`** § **Tool gates vs subprocess / runtime imports**. Use this table before debugging a failing CI step locally.

**Row parity:** this table is purely documentary; the authoritative runnable surface is `tools/harness.py` subcommands.

**Convention (typical):** exit **0** = pass; **1** = policy / contract / scan failure; **2** = environment or precondition (e.g. missing editable install, hygiene sign-off bundle). Some gates use **`raise SystemExit(...)`** instead of `return 1` — treat non-zero the same.

| Subcommand | Needs `pip install -e ".[dev]"`? | Typical exits | Human / doc dependencies |
| --- | --- | --- | --- |
| `audit-internal-link` | No | 0 / 1 | internal `docs/` links |
| `branch-protection-drift` | No | 0 / 1 | `git`; optional `gh` + `GITHUB_TOKEN` for live API |
| `check-exclusions` | No | 0 / 1 | **`docs/repo_exclusions.md`**, `docs/audit_path_map.md` Scope |
| `ci-lane-responsibility` | No | 0 | `docs/ci_gate_matrix.md` |
| `compat-switch-expiry` | **Yes** | 0 / 1 / **2** | `docs/ci_gate_matrix.md` § runtime imports |
| `contract-manifest` | No | 0 / 1 | `docs/audit_path_map.md`, `.github/workflows/ci.yml`, API/README docs |
| `doc-preamble-hygiene` | No | 0 / 1 | optional bilingual preamble order (`docs/documentation_styleguide.md` § Part B.1); default warn-only — use `--enforce` to fail |
| `failure-surface-triage` | No | 0 | failure surface taxonomy docs |
| `format-check` | **Yes** | 0 / 1 | `python -m black --check .` (wrapped) |
| `hygiene` | No | 0 / 2 | `git`; sign-off dirs per gate docstring |
| `import-topology` | No | 0 / 1 | `tools/gen_lirix_import_graph.py --check` (wrapped) |
| `legacy-sunset` | No | 0 | `pyproject.toml`, `lirix/__init__.py` |
| `lint` | **Yes** | 0 / 1 | `python -m ruff check .` (wrapped) |
| `migration-observability-report` | **Yes** | 0 / 1 | `tools/migration_observability_report.py` (wrapped) |
| `no-internal-imports` | No | 0 / 1 | markdown import examples |
| `phase-exit-checklists` | No | 0 / 1 | checklist paths under `docs/` |
| `plan-to-pr-exit-metrics` | No | 0 | plan metrics docs / conventions |
| `registry-authority-contract` | **Yes** (`import lirix`) | 0 / 1 / **2** | `docs/ci_gate_matrix.md` § runtime imports |
| `release-notes-gate` | No | 0 / 1 | `docs/release_notes.md` required substrings |
| `required-check-policy` | No | 0 / 1 | `docs/branch_protection_required_checks.md` |
| `root-import-surface` | **Yes** | 0 / 1 / **2** | same |
| `test-compat-matrix` | **Yes** | 0 / 1 | marker-filtered pytest subset (`ci.yml` compatibility matrix) |
| `test-coverage-required` | **Yes** | 0 / 1 | full pytest + coverage (`fail_under` in `pyproject.toml`) |
| `test-governance` | **Yes** | 0 / 1 | explicit governance pytest list (`tools/validators.py` SSOT) |
| `test-monkeypatch-convention` | No | 0 / 1 | `tests/` monkeypatch style |
| `test-pr-compat-smoke` | **Yes** | 0 / 1 | PR matrix smoke subset (`ci.yml`) |
| `test-topology-admission` | No | 0 / 1 | env `TEST_TOPOLOGY_*` (see `ci.yml`) |
| `typecheck` | **Yes** | 0 / 1 | `python -m mypy --strict lirix` (wrapped) |

### 中文

**中文：** 所有门禁已聚合到单一入口：`python tools/harness.py <subcommand>`。
所有门禁逻辑已统一重构至 `tools/validators.py` 的原生函数，原 18 个独立 gate 脚本已彻底废弃。

与 **`docs/ci_gate_matrix.md`** 中 **Tool gates vs subprocess / runtime imports** 一节配套；本地复现 CI 失败前先查本表。体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

**主表与 Row parity / Convention**：权威英文主表及行数约定、退出码惯例均在上方 **`### English`**，避免在「中文」小节标题下铺满英文正文。

**表头列释义**（与英文主表列一一对应）：

- **Subcommand**：传给 `python tools/harness.py` 的子命令名。
- **Needs `pip install -e ".[dev]"`?**：是否需先以可编辑方式安装开发依赖。
- **Typical exits**：典型退出码（0 通过；1 策略/契约/扫描失败；2 环境或前置条件不满足等）。
- **Human / doc dependencies**：人工或文档侧依赖（外部命令、环境变量、SSOT 文档路径等）。

## Related tools (also exposed as harness subcommands)

| Script | Harness mirror | Notes |
| --- | --- | --- |
| `gen_lirix_import_graph.py` | `import-topology` | Regenerate **`docs/lirix_import_topology.md`**; CI uses **`--check`**. |
| `migration_observability_report.py` | `migration-observability-report` | Writes migration observability artifacts (Fast Required). |
