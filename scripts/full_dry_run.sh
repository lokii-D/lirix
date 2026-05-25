#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Mantle harness dry-run (delegates to mantle_TT SSOT)..."
bash "${ROOT}/scripts/mantle/validate_harness.sh"
bash "${ROOT}/mantle_TT/scripts/pack_bundle.sh"
echo "✅ Dry-run complete. Optional: docker compose -f mantle_TT/docker-compose.yml up --build"
