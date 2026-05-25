#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
DEFAULT_PYTHON="$REPO_ROOT/.venv/bin/python"
if [[ -x "$DEFAULT_PYTHON" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi
export MANTLE_RPC_URLS="${MANTLE_RPC_URLS:-https://rpc.mantle.xyz,https://mantle.drpc.org,https://rpc.ankr.com/mantle}"
export LIRIX_DEMO_ALLOWLIST="1"
export PYTHONPATH="${PYTHONPATH:-$REPO_ROOT}"

exec "$PYTHON_BIN" "$ROOT_DIR/examples/mantle_defi_demo.py"
