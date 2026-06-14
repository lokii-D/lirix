#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${ROOT}/dist"
TAR_PATH="${ROOT}/dist/mantle-turing-2026-harness.tar.gz"

tar -czf "${TAR_PATH}" \
  -C "${ROOT}" \
  README_submission.md .env.example app.py Dockerfile.submission docker-compose.yml \
  requirements_submission.txt contracts/ scripts/ docs/ tests/mantle/ \
  .github/workflows/ci.yml .gitignore

# Bundle summary for judges
FILE_COUNT=$(tar -tzf "${TAR_PATH}" | wc -l | tr -d ' ')
SCREENSHOT_COUNT=$(tar -tzf "${TAR_PATH}" 'docs/submission_assets/*.png' 2>/dev/null | wc -l | tr -d ' ')
TAR_SIZE=$(du -h "${TAR_PATH}" | cut -f1)

echo ""
echo "📦 Bundle summary"
echo "   Path:        ${TAR_PATH}"
echo "   Size:        ${TAR_SIZE}"
echo "   Files:       ${FILE_COUNT}"
echo "   Screenshots: ${SCREENSHOT_COUNT} PNG(s) in docs/submission_assets/"
echo "   Entry:       README_submission.md"
echo "   Evidence:    mantle_TT/external_evidence.md (in full repo clone)"
printf '✅ Pack complete → %s\n' "${TAR_PATH}"
