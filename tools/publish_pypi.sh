#!/usr/bin/env bash
# Local one-shot: build sdist+wheel, twine check, upload to PyPI (API token).
#
# One command (token never belongs in git — use env for this shell only):
#   PYPI_TOKEN='pypi-…' ./tools/publish_pypi.sh
#
# Equivalent explicit form:
#   TWINE_USERNAME=__token__ TWINE_PASSWORD='pypi-…' ./tools/publish_pypi.sh
#
# Requires: network; token with "Upload packages" for project `lirix`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYPI_TOKEN:-}" && -z "${TWINE_PASSWORD:-}" ]]; then
  export TWINE_PASSWORD="${PYPI_TOKEN}"
fi
: "${TWINE_PASSWORD:?Missing credentials. Set PYPI_TOKEN or TWINE_PASSWORD to your PyPI API token.}"
export TWINE_USERNAME="${TWINE_USERNAME:-__token__}"

PYTHON="${ROOT}/.venv_ci312/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${ROOT}/.venv/bin/python"
fi
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

"$PYTHON" -c "import build, twine" 2>/dev/null || "$PYTHON" -m pip install -q build twine

rm -rf dist build
"$PYTHON" -m build --sdist --wheel
"$PYTHON" -m twine check --strict dist/*
"$PYTHON" -m twine upload dist/* --non-interactive

echo "[publish_pypi] OK — uploaded $(basename "$ROOT") to PyPI (verify: https://pypi.org/project/lirix/)"
