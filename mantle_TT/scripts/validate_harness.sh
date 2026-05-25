#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${ROOT_DIR}/.." && pwd)"

echo "🔍 Mantle harness validation (mantle_TT SSOT)..."

bash "${SCRIPT_DIR}/validate_bundle.sh"
bash "${SCRIPT_DIR}/run_mantle_pytests.sh"

python3 -m ruff check "${ROOT_DIR}" --config "${ROOT_DIR}/pyproject.toml"
python3 -m black --check --quiet --config "${ROOT_DIR}/pyproject.toml" "${ROOT_DIR}"

echo "✅ Mantle harness validation passed"
