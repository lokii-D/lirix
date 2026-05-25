#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "${ROOT}/mantle_TT/scripts/run_mantle_pytests.sh"
