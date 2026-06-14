#!/usr/bin/env bash
# Validation only: bundle, pytest, then lint. No packaging, demo execution, or evidence handling.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

on_fail() {
  local code=$?
  echo ""
  echo "❌ validate_harness failed (exit ${code})"
  echo "   Fix the step above, then re-run: ./scripts/validate_harness.sh"
  echo "   Setup: pip install -e . && pip install -r requirements_submission.txt"
  exit "${code}"
}
trap on_fail ERR

echo "[0/5] sync submission entrypoints (SSOT: mantle_TT/)"
bash "${SCRIPT_DIR}/sync_submission_entrypoints.sh"

echo "[1/5] bundle file check"
python3 - "$ROOT_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = [
    root / "README_submission.md",
    root / ".env.example",
    root / "app.py",
    root / "Dockerfile.submission",
    root / "docker-compose.yml",
    root / "requirements_submission.txt",
    root / "contracts" / "LirixShield.sol",
    root / "scripts",
    root / "docs",
    root / "tests" / "mantle",
    root / ".github" / "workflows" / "ci.yml",
    root / ".gitignore",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    print("Missing bundle inputs:")
    for path in missing:
        print(f"  - {path}")
    raise SystemExit(1)
print("       bundle inputs OK")
PY

echo "[2/5] pytest (tests/mantle only — overrides project addopts)"
python3 -m pytest "${ROOT_DIR}/tests/mantle" -q --tb=line \
  -o addopts="-q --strict-markers --import-mode=importlib"

echo "[3/5] ruff"
python3 -m ruff check \
  "${ROOT_DIR}/README_submission.md" \
  "${ROOT_DIR}/app.py" \
  "${ROOT_DIR}/contracts" \
  "${ROOT_DIR}/docs/2.0.4_orchestrator.md" \
  "${ROOT_DIR}/scripts" \
  "${ROOT_DIR}/tests/mantle" \
  --config "${ROOT_DIR}/pyproject.toml"

echo "[4/5] black"
python3 -m black --check --quiet --config "${ROOT_DIR}/pyproject.toml" \
  "${ROOT_DIR}/app.py" \
  "${ROOT_DIR}/contracts" \
  "${ROOT_DIR}/scripts" \
  "${ROOT_DIR}/tests/mantle"

echo "validate_harness-ok"
