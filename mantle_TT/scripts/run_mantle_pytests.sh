#!/usr/bin/env bash
# Mantle harness pytest entry (SSOT). Invoked from repo root via scripts/mantle/run_pytests.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
GUARD="${REPO_ROOT}/scripts/pytest_guard.py"

if [ ! -f "${GUARD}" ]; then
  echo "missing ${GUARD} (clone full Lirix repo)" >&2
  exit 1
fi

MANTLE_UNIT=(
  mantle_TT/tests/mantle/test_mantle_bundle.py
  mantle_TT/tests/mantle/test_mantle_config_frozen.py
  mantle_TT/tests/mantle/test_mantle_l4_l5.py
  mantle_TT/tests/mantle/test_mantle_orchestrator.py
)
MANTLE_MANTLE_DIR=(
  mantle_TT/mantle/test_mantle_config.py
  mantle_TT/mantle/test_mantle_config_extra.py
  mantle_TT/mantle/test_simulator_mantle.py
  mantle_TT/mantle/test_shadow_auditor_mantle.py
  mantle_TT/mantle/test_shadow_auditor_mantle_extra.py
)

cd "${REPO_ROOT}"
python3 "${GUARD}" \
  --inactivity-seconds 120 \
  --hard-timeout-seconds 900 \
  -- python3 -m pytest \
  -o "addopts=--strict-markers --import-mode=importlib" \
  -q --tb=short \
  "${MANTLE_UNIT[@]}" "${MANTLE_MANTLE_DIR[@]}"
