#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[A] core contract and consistency"
python3 -m pytest -o addopts= -q tests/test_core/test_sync_async_contract_consistency.py
python3 -m pytest -o addopts= -q tests/test_core/test_session_workflow_strict_happy_path.py
python3 -m pytest -o addopts= -q tests/test_core/test_simulate_only_prior_validate_config.py
python3 -m pytest -o addopts= -q tests/test_core/test_public_exports_contract.py
python3 -m pytest -o addopts= -q tests/test_core/test_entrypoint_symbol_binding_contract.py

echo "[B] hook / governance / evidence"
python3 -m pytest -o addopts= -q tests/test_core/test_hook_manager.py
python3 -m pytest -o addopts= -q tests/test_core/test_hook_governance_async_contract_mode_parity.py
python3 -m pytest -o addopts= -q tests/test_core/test_status_aggregation.py
python3 -m pytest -o addopts= -q tests/test_core/test_config_governance_overlap_guards.py

echo "[C] L4/L5 and integration boundaries"
python3 -m pytest -o addopts= -q tests/test_layers/test_l4_rpc_manager_disagreement_report.py
python3 -m pytest -o addopts= -q tests/test_layers/test_l4_rpc_evidence_modes.py
python3 -m pytest -o addopts= -q tests/test_layers/test_shadow_auditor_policy_bundle.py
python3 -m pytest -o addopts= -q tests/integrations/test_langchain_tool.py tests/integrations/test_autogen_tool.py
python3 -m pytest -o addopts= -q tests/test_integration/test_real_e2e_paths.py

echo "[D] gates"
python3 tools/harness.py contract-manifest
python3 tools/harness.py root-import-surface
python3 tools/harness.py test-monkeypatch-convention

echo "[E] full run"
python3 -m pytest -o addopts= -q
