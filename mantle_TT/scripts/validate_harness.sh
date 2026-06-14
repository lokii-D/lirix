#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"

PYTHON="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
fi

echo "🔍 Mantle harness validation (mantle_TT SSOT)..."

bash "${SCRIPT_DIR}/validate_bundle.sh"
bash "${SCRIPT_DIR}/run_mantle_pytests.sh"

"${PYTHON}" -m ruff check "${ROOT_DIR}" --config "${ROOT_DIR}/pyproject.toml"
"${PYTHON}" -m black --check --quiet --config "${ROOT_DIR}/pyproject.toml" "${ROOT_DIR}"

echo "✅ Mantle harness validation passed"
