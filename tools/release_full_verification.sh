#!/usr/bin/env bash
# Release-equivalent local verification chain (aligned with .github/workflows/ci.yml lint job).
# Prerequisites: repo root, Python env with `pip install -e ".[dev]"`, optional `rg` (ripgrep) for release notes gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${RELEASE_SIGNOFF_OUT:-$ROOT/audit_artifacts/release_signoff/$(date +%Y-%m-%d)}"
mkdir -p "$OUT"

echo "[release_full_verification] output dir: $OUT"

echo "[1/10] hygiene_gate"
python tools/harness.py hygiene

echo "[2/10] ruff"
python -m ruff check .

echo "[3/10] black --check"
python -m black --check .

echo "[4/10] mypy --strict lirix"
python -m mypy --strict lirix

echo "[5/10] governance explicit pytest batch (ci.yml lint)"
# shellcheck disable=SC2086
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
  tests/integrations/test_langchain_tool.py

echo "[6/10] release notes gate (rg on docs/release_notes.md)"
if command -v rg >/dev/null 2>&1; then
  rg -n "API Contract Delta" docs/release_notes.md
  rg -n "additive and backward compatible" docs/release_notes.md
else
  echo "WARN: rg not found; skipping phrase grep (see CONTRIBUTING.md)."
fi

echo "[7/10] docs / import / monkeypatch gates"
python tools/harness.py contract-manifest
python tools/harness.py audit-internal-link
python tools/harness.py doc-preamble-hygiene
python tools/harness.py no-internal-imports
python tools/harness.py root-import-surface
python tools/harness.py test-monkeypatch-convention --strict

PY_LOG="$OUT/B4_pytest_full_cov_local.log"
echo "[8/10] full pytest + coverage -> $PY_LOG"
python -m pytest -q --cov=lirix --cov-report=term-missing:skip-covered --cov-report=xml 2>&1 | tee "$PY_LOG"

ACC_JSON="$OUT/B4_release_acceptance_report_local.json"
echo "[9/10] release_acceptance_report -> $ACC_JSON"
python tools/release_acceptance_report.py \
  --log "$PY_LOG" \
  --coverage-threshold 100 \
  --warnings-blocking \
  --signoff-dir "$OUT" | tee "$ACC_JSON"

if [[ "${RUN_ANVIL_E2E:-}" == "1" ]]; then
  if command -v anvil >/dev/null 2>&1; then
    echo "[10/10] optional Anvil E2E (RUN_ANVIL_E2E=1)"
    E2E_LOG="$OUT/B4_real_e2e_anvil_paths_local.log"
    # If anvil is already up, this still works for tests that connect to default port.
    python -m pytest -o addopts= -q tests/test_integration/test_real_e2e_paths.py 2>&1 | tee "$E2E_LOG" || {
      echo "Optional E2E failed; not failing the whole script unless RUN_ANVIL_E2E_STRICT=1"
      if [[ "${RUN_ANVIL_E2E_STRICT:-}" == "1" ]]; then
        exit 1
      fi
    }
  else
    echo "WARN: RUN_ANVIL_E2E=1 but anvil not on PATH; skipping E2E."
  fi
else
  echo "[10/10] skip optional Anvil E2E (set RUN_ANVIL_E2E=1 to run; RUN_ANVIL_E2E_STRICT=1 to fail on E2E errors)"
fi

echo "release_full_verification: OK"
