#!/usr/bin/env bash
# Full Mantle harness dry-run: validate → pack.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STEP=""

on_fail() {
  local code=$?
  echo ""
  echo "❌ Dry-run failed at step: ${STEP:-unknown} (exit ${code})"
  case "${STEP}" in
    validate)
      echo "   → Check missing files listed above (harness branch? repo root?)"
      echo "   → SSOT: edit mantle_TT/README_submission.md and mantle_TT/app.py only"
      echo "   → Install deps: pip install -e . && pip install -r requirements_submission.txt"
      echo "   → Re-run: ./scripts/validate_harness.sh"
      ;;
    pack)
      echo "   → Validation must pass before packing"
      echo "   → Re-run: ./scripts/validate_harness.sh"
      ;;
    *)
      echo "   → See scripts/README.md for judge priority path and troubleshooting"
      ;;
  esac
  exit "${code}"
}
trap on_fail ERR

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Lirix 2.0.4 · Mantle harness dry-run"
echo "  Root: ${ROOT}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

STEP="validate"
echo "▶ Step 1/2: validate (bundle + pytest + lint)"
bash "${ROOT}/scripts/validate_harness.sh"
echo ""

STEP="pack"
echo "▶ Step 2/2: pack submission bundle"
bash "${ROOT}/scripts/pack_bundle.sh"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Dry-run complete"
echo "   Next: docker compose up --build  (optional local demo)"
echo "   Demo: https://huggingface.co/spaces/lokiii07/lirix-mantle-harness"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
