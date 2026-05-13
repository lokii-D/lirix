# Release sign-off audit artifacts

**EN:** Versioned evidence bundles for release sign-off; local replay commands and minimum artifact set below.
**中文：** 发布签核用的版本化、可复核、可复现证据包；本地回放命令与最低证据集见下文。体例见 [`docs/documentation_styleguide.md`](../../docs/documentation_styleguide.md)。

### English

This directory contains **versioned, reviewable, and reproducible** evidence bundles for release sign-off.

### 中文

本目录包含用于发布签署的**版本化、可审查、可复现**证据束。

- **Local rehearsal:** follow § **How to generate (local CI-equivalent replay)** below (stepwise `tee` under a date folder; same semantics as [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) Fast Required + coverage + acceptance JSON; see also [`docs/release_pr_checklist.md`](../../docs/release_pr_checklist.md)).
- **Brief template:** [`B4_local_ci_equivalent_brief.TEMPLATE.md`](B4_local_ci_equivalent_brief.TEMPLATE.md) — copy into your date folder as `B4_local_ci_equivalent_brief.md` and fill placeholders.

- **Location**: `audit_artifacts/release_signoff/<YYYY-MM-DD>/`
- **Allowed artifact types**: text only (`.md`, `.log`, `.json`)
- **Non-goals**: do not commit virtualenvs, caches, coverage DBs, or large binary blobs.

## Bundle structure

Each bundle lives under a date folder:

- `audit_artifacts/release_signoff/2026-05-10/`
  - `B4_local_ci_equivalent_brief.md`
  - `R1_deprecation_warning_baseline.md`
  - `C5_coverage_100_verification.md`
  - Selected logs that prove CI-equivalent execution (see “Minimum evidence set”).

## Minimum evidence set (must-have)

Inside `audit_artifacts/release_signoff/<date>/`:

- **Briefs / summaries**
  - `B4_local_ci_equivalent_brief.md`
  - `R1_deprecation_warning_baseline.md`
  - `C5_coverage_100_verification.md`
- **Acceptance verdict (single-source JSON)**
  - `B4_release_acceptance_report_*.json` (includes **`recommended_artifacts_present`**: machine-readable hints for optional E2E/perf files in the same date folder; see [`docs/release_pr_checklist.md`](../../docs/release_pr_checklist.md))
- **Key logs (at least one per category)**
  - Governance explicit gate: `B4_governance_gate_explicit_pytest*.log`
  - Full warnings baseline: `C4_full_pytest_warnings_baseline*.log`
  - CI-equivalent full pytest + coverage: `B4_pytest_full_cov*.log`
  - Release notes gate: `B4_release_notes_gate_*.log`
  - (If enabled in CI) MyPy strict: `B4_mypy_strict_lirix*.log`
  - (Optional) Compileall: `B3_compileall*.log`
- **Recommended (release-grade path proofs)**
  - Real Anvil E2E log: `B4_real_e2e_anvil_paths_*.log` (or documented skip — see “Real E2E” below)

## How to generate (local CI-equivalent replay)

The goal is to reproduce the **semantics** of `.github/workflows/ci.yml` locally (especially the `lint` job) in a clean
Python environment, and to capture logs as immutable evidence.

### Environment setup (recommended)

Use an isolated venv, aligned with CI Python 3.12:

```bash
python3.12 -m venv .venv_ci312
source .venv_ci312/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### CI-equivalent commands (capture logs)

Set `OUT` (or `RELEASE_SIGNOFF_OUT`) to `audit_artifacts/release_signoff/<date>/` and run the same steps as in `.github/workflows/ci.yml`, piping each command through `tee` so filenames match historical bundles:

Run the same steps as in `.github/workflows/ci.yml` and write logs under the date folder:

```bash
DATE="2026-05-10"
OUT="audit_artifacts/release_signoff/$DATE"
mkdir -p "$OUT"

python -m ruff check . 2>&1 | tee "$OUT/B4_ruff_ci312.log"
python -m black --check . 2>&1 | tee "$OUT/B4_black_check_ci312.log"
python -m mypy --strict lirix 2>&1 | tee "$OUT/B4_mypy_strict_lirix_ci312.log"

python -m pytest -q \
  tests/test_core/test_canonical_semantics.py \
  tests/test_core/test_agent_feedback_reason_taxonomy_closure.py \
  tests/test_core/test_config_governance_overlap_guards.py \
  tests/test_core/test_session.py \
  tests/test_core/test_session_replay_verifier_malformed_shapes.py \
  tests/test_core/test_session_workflow_strict_happy_path.py \
  tests/test_core/test_simulate_only_prior_validate_config.py \
  tests/test_core/test_evidence_models.py \
  tests/test_core/test_chain_adapter_profiles.py \
  tests/test_core/test_plan_alignment_hardening_coverage.py \
  tests/test_core/test_replay_registry_closure_binding.py \
  tests/test_core/test_replay_registry_closure_parity_all_entrypoints.py \
  tests/test_core/test_hook_governance_async_contract_mode_parity.py \
  tests/test_core/test_hook_manager.py \
  tests/test_core/test_status_aggregation.py \
  tests/test_core/test_entrypoints.py \
  tests/test_core/test_entrypoint_symbol_binding_contract.py \
  tests/test_core/test_public_exports_contract.py \
  tests/test_layers/test_l4_rpc_manager_disagreement_report.py \
  tests/test_layers/test_l4_rpc_evidence_modes.py \
  tests/test_layers/test_shadow_auditor_policy_bundle.py \
  tests/test_integrations/test_langchain_tool_invoke_guardian_plain_string_result_policy_merge.py \
  2>&1 | tee "$OUT/B4_governance_gate_explicit_pytest_ci312.log"

rg -n "API Contract Delta" docs/release_notes.md 2>&1 | tee "$OUT/B4_release_notes_gate_1_ci312.log"
rg -n "additive and backward compatible" docs/release_notes.md 2>&1 | tee "$OUT/B4_release_notes_gate_2_ci312.log"

python tools/harness.py contract-manifest 2>&1 | tee "$OUT/B4_docs_contract_gate_contract_manifest_ci312.log"
python tools/harness.py audit-internal-link 2>&1 | tee "$OUT/B4_audit_internal_link_gate_ci312.log"
python tools/harness.py doc-preamble-hygiene 2>&1 | tee "$OUT/B4_doc_preamble_hygiene_gate_ci312.log"
python tools/harness.py no-internal-imports 2>&1 | tee "$OUT/B4_no_internal_imports_gate_ci312.log"
python tools/harness.py root-import-surface 2>&1 | tee "$OUT/B4_root_import_surface_gate_ci312.log"
python tools/harness.py test-monkeypatch-convention --strict 2>&1 | tee "$OUT/B4_monkeypatch_convention_gate_strict_ci312.log"

python -m pytest -q --cov=lirix --cov-report=term-missing:skip-covered --cov-report=xml \
  2>&1 | tee "$OUT/B4_pytest_full_cov_ci312.log"

# Single-source acceptance verdict (tests passed / coverage 100% / warnings must be zero)
python tools/release_acceptance_report.py \
  --log "$OUT/B4_pytest_full_cov_ci312.log" \
  --coverage-threshold 100 \
  --warnings-blocking \
  2>&1 | tee "$OUT/B4_release_acceptance_report_ci312.json"
```

**Release sign-off requires `--warnings-blocking`**: the emitted JSON must show `criteria.warnings_blocking: true` and
`metrics.warnings: 0`, otherwise `evaluation.release_ok` is false even when coverage passes.

## Real E2E (Anvil + fork helpers) — release policy

Default **GitHub Actions** workflows do **not** require a live Anvil-backed machine for every job; some matrix legs rely on mocks only.

For **release sign-off**, you must either:

1. **Run and capture** the real E2E suite with Anvil available (Foundry `anvil` on `PATH`), and store the log under the same date folder:

```bash
DATE="2026-05-10"
OUT="audit_artifacts/release_signoff/$DATE"
python3 -m pytest -o addopts= -q tests/test_integration/test_real_e2e_paths.py \
  2>&1 | tee "$OUT/B4_real_e2e_anvil_paths_ci312.log"
```

2. **Or** document an explicit skip with reason (machine has no Foundry / CI-only bundle): add a one-line note to `B4_local_ci_equivalent_brief.md` in that date folder stating that E2E was skipped, with the marker `E2E_SKIP_REASON=...`.

Recommended optional artifact name: `B4_real_e2e_anvil_paths_*.log`.

## Performance baseline (realistic fixture profile)

Quick gate (always on): `tests/test_core/test_pipeline_performance_gates.py::test_main_paths_realistic_fixture_quick_gate_budgets`.

**Semantics:** these gates measure **upper bounds on local / monkeypatched pipeline paths** (orchestration + evidence emission), not end-to-end latency to public RPC endpoints. Production tail latency requires separate observability; see also the README § Quantifiable Value Signals.

Optional sign-off JSON (non-blocking collection):

```bash
DATE="2026-05-10"
OUT="audit_artifacts/release_signoff/$DATE"
export LIRIX_RUN_PERF_REALISTIC_BASELINE=1
export LIRIX_PERF_REALISTIC_BASELINE_JSON_OUT="$OUT/B4_perf_baseline_realistic_fixture_ci312.json"
python3 -m pytest -o addopts= -q \
  tests/test_core/test_pipeline_performance_gates.py::test_main_paths_realistic_fixture_baseline_report
python3 tools/release_perf_baseline_report.py --json "$OUT/B4_perf_baseline_realistic_fixture_ci312.json" --out "$OUT/B4_perf_baseline_realistic_fixture_ci312.normalized.json"
```

Commit the normalized JSON if you want a stable diff; either file satisfies “perf baseline captured”.

## Warnings baseline (DeprecationWarning policy)

The migration window policy and expected counts are recorded in:

- `R1_deprecation_warning_baseline.md`

The authoritative baseline logs are referenced from that document (typically `C4_full_pytest_warnings_baseline*.log`).

## Coverage policy (authoritative threshold)

- **Release + CI**: **`pyproject.toml` → `[tool.coverage.report].fail_under = 100`** on `lirix/` (pytest-cov reads this via Coverage.py).
- **Closure semantics**: documented in `C5_coverage_100_verification.md` (tail/branch closure suites complement the numeric gate).
- **Acceptance JSON**: run with **`--coverage-threshold 100`** and **`--warnings-blocking`** (sign-off policy). The committed
  template defaults in the script remain permissive for local triage; **do not** use those defaults for release bundles.
