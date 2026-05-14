---
title: Release final multiscan harness (R3 master)
purpose: multi-wave redundant pre-release audit + Cursor handoff schema; supersedes informal prior rounds
---

# Release final multiscan harness (R3 master)

**EN:** Treat this document as the **operational SSOT for the last human/agent multiscan** before tagging. Do **not** carry forward undocumented assumptions from earlier chats: the only binding verdict is **evidence** produced by the next execution pass (local logs + this report template).
**中文：** 本文档是 **发布前最后一轮多波次核查的操作 SSOT**。不要沿用未写入证据链的口头结论；**唯一裁决**来自下一轮实际跑出来的日志 + 下文「核查报告模板」。

Companion procedural docs: [`release_pr_checklist.md`](release_pr_checklist.md), [`audit_artifacts/release_signoff/README.md`](../audit_artifacts/release_signoff/README.md), [`ci_gate_matrix.md`](ci_gate_matrix.md), [`tools_gates_index.md`](tools_gates_index.md).

---

## 1. Scope definition — what “outside ignore” means

| Layer | Mechanism | Meaning for this harness |
| --- | --- | --- |
| Git index | `git ls-files` | **Primary audit universe** — every tracked path is in scope. |
| Ignore files | `.gitignore`, `.harnessignore` | Defines what **must not appear as tracked** (e.g. `__pycache__/`, `cache/**`, venv trees). Hygiene must stay green. |
| Documented exclusions | `docs/repo_exclusions.md`, `docs/audit_path_map.md` § Scope | Paths intentionally **out of default CI** (e.g. `tdsc/`, `mantle_TT/`): still verify they are **not accidentally tracked** and four-way tokens stay aligned. |
| Pytest collection | `pyproject.toml` → `norecursedirs` | Tests must not recurse into excluded trees; cross-check when adding top-level dirs. |

**Redundant rule:** run both `python tools/harness.py hygiene` (forbidden tracked globs + sign-off allowlist) and a manual `git ls-files \| grep -E '__pycache__|\.pyc|\.egg-info|node_modules|\.venv'` (expect **empty**).

---

## 2. Repository fingerprint (snapshot for Cursor — refresh before each round)

Regenerate counts on the agent host; numbers below are **illustrative class** (as of harness authorship): ~372 tracked paths total; dominant buckets: `tests/` (~203), `lirix/` (~61 `.py` plus `py.typed`), `docs/` (~41), `.github/` (~12), `tools/` (~10), `examples/` (4), root policy files, `contracts/`, optional workflows.

### 2.1 `lirix/` Python modules (complete — any omission in narrative docs is a doc bug)

```text
lirix/__init__.py, __main__.py, cli.py, _client_facade.py, _facade.py, _layer_factories.py, _multicall_facade.py
lirix/_client_core/__init__.py
lirix/audit/__init__.py, logger.py
lirix/core/__init__.py, builder.py, calldata_builder.py, canonical_taxonomy.py, chain_adapter.py, client_components.py,
  compat.py, config.py, config_authority.py, config_fingerprint.py, config_governance.py, constants.py, contracts.py,
  decoder_registry.py, evidence.py, evidence_semantics.py, exceptions.py, failure_protocol.py, forensic_verifier.py,
  hook_contract.py, hook_manager.py, layer_ports.py, multicall.py, orchestrator.py, pipeline_protocol.py,
  registry_authority.py, registry_profile_guard.py, session.py, session_fsm.py, signatures.py, status_aggregation.py,
  trace_recorder.py
lirix/intents/__init__.py, translator.py
lirix/integrations/__init__.py, autogen/__init__.py, autogen/tool.py, langchain/__init__.py, langchain/tool.py
lirix/layers/__init__.py, l1_intent_validator.py, l2_schema_validator.py, l3_defi_parser.py, l3_proxy_piercer.py,
  l4_rpc_manager.py, l5_sandbox_simulator.py, l5_shadow_auditor.py
lirix/registry/__init__.py, bridges.py
lirix/shield/simulator.py
lirix/py.typed
```

**Cross-check:** `docs/STRUCTURE.md` tree is **not exhaustive** (e.g. it omits `l5_shadow_auditor.py`, `shield/`, `intents/`, facades). When editing structure docs, diff against this list.

### 2.2 Workflows (all under `.github/workflows/`)

| File | Role |
| --- | --- |
| `ci.yml` | Fast Required + Coverage Required + PR smoke + compat matrix |
| `governance-lane.yml` | Scheduled / governance-only gates |
| `slow-lane-schedule.yml` | Slow scheduled checks |
| `release.yml` | Release publication automation |
| `e2e-anvil-optional.yml` | Optional Anvil E2E |
| `mantle_fork_smoke.yml` | Optional Mantle fork (secrets) |
| `sbom-optional.yml` | Optional SBOM |

**Redundant rule:** for any change to `ci.yml` step order or gate set, update **`docs/ci_gate_matrix.md`**, **`docs/documentation_styleguide.md`** (Fast Required doc-block rule), and run **`python tools/harness.py contract-manifest`**.

### 2.3 `tools/` surface

| Artifact | Role |
| --- | --- |
| `harness.py` | Single router; `COMMANDS` keys must match `docs/tools_gates_index.md` main table row count |
| `validators.py` | All gate implementations + governance pytest SSOT |
| `contract_manifest_gate.py`, `ci_gate_shared.py` | Doc/CI contract enforcement |
| `gen_lirix_import_graph.py` | Import topology generator / `--check` |
| `migration_observability_report.py`, `release_acceptance_report.py`, `cv_score_report.py`, `release_perf_baseline_report.py` | Reports / scoring |
| `final_regression_template.sh` | Local release rehearsal wrapper |

---

## 3. Grading rubric (100-point — all binary; any fail = not ship-ready)

| # | Criterion | Evidence |
| --- | --- | --- |
| G1 | **Zero forbidden tracked artifacts** | `python tools/harness.py hygiene` exit 0 |
| G2 | **Exclusions four-way consistency** | `python tools/harness.py check-exclusions` exit 0 |
| G3 | **Import topology frozen + preflight worktree** | `python tools/harness.py preflight-remediation-status` exit 0 (includes `gen_lirix_import_graph.py --check`; superset of legacy `import-topology`) |
| G4 | **Lint / format / strict types** | `lint`, `format-check`, `typecheck` exit 0 |
| G5 | **Governance pytest SSOT** | `test-governance` exit 0 |
| G6 | **Registry + release notes + manifest + policy** | `registry-authority-contract`, `release-notes-gate`, `contract-manifest`, `required-check-policy`, `ci-lane-responsibility`, `compat-switch-expiry`, `plan-to-pr-exit-metrics` all exit 0 |
| G7 | **Docs integrity** | `audit-internal-link`; `doc-preamble-hygiene` (use `--enforce` locally for strict) |
| G8 | **Import / test discipline** | `no-internal-imports`, `root-import-surface`, `test-monkeypatch-convention --strict`, `test-topology-admission` |
| G9 | **Migration observability** | `migration-observability-report` exit 0 |
| G10 | **Full tests + coverage 100%** | `python tools/harness.py test-coverage-required` exit 0; `pyproject.toml` `fail_under = 100` |
| G11 | **Warnings as errors** | `filterwarnings = ["error"]` respected; no third-party noise without explicit narrow ignores |
| G12 | **Acceptance JSON** | `tools/release_acceptance_report.py` with `--coverage-threshold 100` and `--warnings-blocking`; `evaluation.release_ok: true` |
| G13 | **Optional lanes sanity** | At least dry-read `e2e-anvil-optional.yml` / `release.yml` for secret / permission drift when touching related code |
| G14 | **UX / narrative coherence** | README + `docs/quickstart.md` + `docs/api_reference.md` + `docs/release_notes.md` roles distinct; bilingual headers per `documentation_styleguide.md` |

---

## 4. Multi-wave execution plan (intentional redundancy)

Execute in order; **each wave uses a different “lens”** on the same artifacts. Do not skip waves because a prior wave “felt clean.”

### Wave A — Index integrity (machine)

1. `python tools/harness.py hygiene`
2. `python tools/harness.py check-exclusions`
3. `python tools/harness.py preflight-remediation-status`
4. `git status` — must be clean for release commit (or only intentional versioned edits)
5. `git ls-files \| wc -l` and spot-check for unexpected new top-level directories

### Wave B — Static quality (machine)

1. `python -m pip install -e ".[dev]"`
2. `python tools/harness.py lint`
3. `python tools/harness.py format-check`
4. `python tools/harness.py typecheck`
5. Repeat **B2–B4** after any doc-only edit (ruff/black sometimes touch generated paths — ensures deterministic)

### Wave C — Policy / contract engines (machine)

Run **alphabetically** to reduce operator bias (same end state as CI):

`audit-internal-link`, `ci-lane-responsibility`, `compat-switch-expiry`, `contract-manifest`, `doc-preamble-hygiene` (add `--enforce` for strict local), `migration-observability-report`, `no-internal-imports`, `plan-to-pr-exit-metrics`, `registry-authority-contract`, `release-notes-gate`, `required-check-policy`, `root-import-surface`, `test-monkeypatch-convention --strict`, `test-topology-admission`

Then: `python tools/harness.py test-governance`

### Wave D — Full runtime proof (machine, longest)

1. `python tools/harness.py test-coverage-required`
2. `python tools/release_acceptance_report.py` (per signoff README flags)
3. `bash tools/final_regression_template.sh` (if maintainers use consolidated rehearsal)

### Wave E — Cross-read: public hull vs internals (human/agent)

1. Read `lirix/__init__.py` exports + `tests/test_core/test_public_exports_contract.py` intent
2. Skim `lirix/_facade.py` pipeline + `tests/test_core/test_readme_envelope_contract.py`
3. Skim `lirix/cli.py` UX paths + `tests/test_cli_ignition_coverage.py`

### Wave F — Layers L1–L5 + shield + shadow (human/agent spot logic)

For **each** file in §2.1 under `layers/`, `shield/`, `core/orchestrator.py`, `core/session.py`: confirm `docs/audit_path_map.md` or `checklist_implementation_matrix.md` has a **row or child mention**; if not, file a doc gap (not necessarily code gap).

### Wave G — Integrations optional deps (human/agent)

1. `lirix/integrations/langchain/tool.py` + `tests/test_integrations/test_langchain_tool_*`
2. `lirix/integrations/autogen/tool.py` + parallel tests
3. Confirm `pyproject.toml` extras `langchain` / `simulation` match README install lines

### Wave H — Packaging boundary (machine + human)

1. `MANIFEST.in` prunes `tests`, `tools`, `examples`, `docs/baselines`, `.github`
2. `python -m build` then inspect `dist/` contents (never commit `dist/`)
3. Confirm `[tool.setuptools.packages.find] exclude` matches non-shipping trees

### Wave I — CI YAML diff audit (human)

1. Compare `ci.yml` job `fast_required` step list to `docs/ci_gate_matrix.md` table row **verbatim order** where styleguide requires parity
2. For each workflow in §2.2: confirm `permissions:`, `concurrency:`, pin hashes on `uses:` actions

### Wave J — Documentation set UX (human)

| Doc | Intended reader | Failure mode |
| --- | --- | --- |
| `README.md` | First landing / GitHub | Duplicates entire API surface |
| `CONTRIBUTING.md` | Contributors | Missing harness entry |
| `SECURITY.md` | Reporters | Stale contact |
| `docs/quickstart.md` | Timeboxed onboarding | Drift from actual defaults |
| `docs/api_reference.md` | API consumers | Contradicts `Lirix` methods |
| `docs/release_notes.md` | Upgraders | Missing gate substrings |
| `docs/troubleshooting.md` | Operators | Orphan links |
| Governance hub (`audit_path_map.md`, `ci_gate_matrix.md`) | Maintainers | Missing new gate row |

### Wave K — Red team: redundancy hunt (human)

Ask: “If I delete this file, does CI still pass?” — for `tools/*`, `docs/*.json` machine contracts, `tests/test_tools/*`. Anything **true dead** → remove; anything **false dead** → document why it exists in `docs/architecture_evolution_action_list.md` or close the ticket.

### Wave L — Final sign-off bundle (human)

Produce / refresh `audit_artifacts/release_signoff/<YYYY-MM-DD>/` per [`audit_artifacts/release_signoff/README.md`](../audit_artifacts/release_signoff/README.md).

---

## 5. Cross-coverage matrix (subsystem × verification)

| Subsystem | Unit / layer tests | Tool gate | Doc anchor |
| --- | --- | --- | --- |
| Public exports | `test_public_exports_contract.py` | `root-import-surface` | `README.md`, `api_reference.md` |
| Broadcast invariant | `test_readme_envelope_contract.py`, LangChain tests | `contract-manifest` | `audit_path_map.md` |
| Hooks / sandbox | `test_hook_*`, `test_hook_plugin_sandbox.py` | governance list | `architecture_control_plane.md` |
| L3 DeFi parser | `test_l3_defi_parser*.py` | *(implicit via full pytest)* | `supported_tx_shapes.md` |
| L4 RPC | `test_l4_rpc_manager*.py` | *(implicit)* | `failure_surface_triage.md` |
| L5 sandbox + revert decode | `test_sandbox_simulator*.py`, `test_l5_sandbox*.py` | *(implicit)* | `evidence_schema_v2.md` |
| Shadow auditor | `test_shadow_auditor*.py` | *(implicit)* | policy docs |
| Registry bridges | `test_bridges.py` | `registry-authority-contract` | `audit_path_map.md` |
| CLI | `test_cli_ignition*.py`, `test_core/test_cli_public_contract.py` | *(implicit)* | `README.md` |
| Toolchain meta | `tests/test_tools/*` | each `harness.py` subcommand | `tools_gates_index.md` |

---

## 6. Handoff report template (fill on **next** Cursor round — paste as top-level reply)

```markdown
## Lirix R3 verification report (date: YYYY-MM-DD, commit: <full sha>)

### A. Machine log summary
- [ ] Wave A (hygiene / exclusions / preflight-remediation-status): PASS/FAIL — attach log snippet
- [ ] Wave B (ruff / black / mypy): PASS/FAIL
- [ ] Wave C (full harness policy batch + test-governance): PASS/FAIL
- [ ] Wave D (test-coverage-required + release_acceptance_report): PASS/FAIL — coverage %, warnings count

### B. Grading rubric §3
- G1–G14: list each PASS/FAIL with one-line evidence

### C. Tracked-tree anomalies
- Unexpected files: <none | list>
- Empty files / empty dirs: <none | list>
- Duplicated scripts or Makefile vs harness drift: <none | list>

### D. Doc / UX gaps
- README vs quickstart overlap: <ok | issue>
- STRUCTURE.md vs §2.1 list drift: <ok | issue + diff>
- Broken internal links: <none | list>

### E. CI / workflow risks
- Pin drift / permission inflation: <none | list>
- Optional workflows affected by this release: <n/a | notes>

### F. Residual risks (must be empty or explicitly accepted)
- <none | numbered list with owner + follow-up issue>

### G. Verdict
- SHIP / NO-SHIP — one sentence rationale
```

---

## 7. Next-round harness evolution (when report shows gaps)

1. Append **new rows** to §5 matrix for any subsystem discovered without a column.
2. If a new top-level directory appears: apply **`docs/repo_exclusions.md`** four-way rule.
3. If a new `tools/harness.py` subcommand appears: update **`docs/tools_gates_index.md`** and **`tools/contract_manifest_gate.py`** floor constants as required.
4. Re-run **`python tools/harness.py contract-manifest`** before merging harness doc edits.

---

## 8. Explicit “do not forget” buckets (common agent blind spots)

- **`audit_artifacts/`** — only `audit_artifacts/release_signoff/**` may be tracked; anything else fails hygiene.
- **`tests/INTERNAL_IMPORT_ALLOWLIST.txt` / `MICRO_TEST_ALLOWLIST.txt`** — tamper implies governance intent; review on any edit.
- **`examples/*.py`** — must remain runnable narratives; cross-check imports with `root-import-surface` philosophy.
- **`contracts/Reverter.sol` + `foundry.toml`** — Foundry cache must **not** be tracked; local `cache/` is gitignored; CI optional lanes compile as needed.
- **`pyproject.toml` `filterwarnings = ["error"]`** — adding library upgrades may require **narrow** `ignore:` entries; never blanket-disable.
- **`Makefile` `test` target** runs `pytest tests/` **without** the harness coverage driver — treat **`test-coverage-required`** as the release authority, not `make test` alone.

---

## 9. Single-block local replay (copy-paste)

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python tools/harness.py hygiene
python tools/harness.py check-exclusions
python tools/harness.py preflight-remediation-status
python -m pip install -U pip
python -m pip install -e ".[dev]"
python tools/harness.py lint
python tools/harness.py format-check
python tools/harness.py typecheck
python tools/harness.py test-governance
python tools/harness.py registry-authority-contract
python tools/harness.py release-notes-gate
python tools/harness.py contract-manifest
python tools/harness.py required-check-policy
python tools/harness.py ci-lane-responsibility
python tools/harness.py compat-switch-expiry
python tools/harness.py plan-to-pr-exit-metrics
python tools/harness.py audit-internal-link
python tools/harness.py doc-preamble-hygiene --enforce
python tools/harness.py no-internal-imports
python tools/harness.py root-import-surface
python tools/harness.py test-monkeypatch-convention --strict
python tools/harness.py test-topology-admission
python tools/harness.py migration-observability-report
python tools/harness.py test-coverage-required
```

---

**End of R3 master harness.** After filling §6 for this repo state, archive the report under `audit_artifacts/release_signoff/<date>/` if your process requires permanent evidence.
