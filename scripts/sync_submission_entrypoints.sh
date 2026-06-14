#!/usr/bin/env bash
# Mirror harness entrypoints from mantle_TT/ (SSOT) to repo root for dry-run / pack.
# Edit only mantle_TT/README_submission.md and mantle_TT/app.py — never hand-edit root copies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSOT="${ROOT}/mantle_TT"

sync_one() {
  local name="$1"
  local src="${SSOT}/${name}"
  local dst="${ROOT}/${name}"
  if [[ ! -f "${src}" ]]; then
    echo "❌ SSOT missing: ${src}"
    echo "   Create or restore mantle_TT/${name} first."
    exit 1
  fi
  cp -f "${src}" "${dst}"
  if ! cmp -s "${src}" "${dst}"; then
    echo "❌ Sync verify failed for ${name}"
    exit 1
  fi
}

sync_one "README_submission.md"
sync_one "app.py"
echo "sync_submission_entrypoints-ok (SSOT: mantle_TT/)"
