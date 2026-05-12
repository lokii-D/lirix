#!/usr/bin/env bash
# Trigger `.github/workflows/release.yml` via workflow_dispatch (same as web "Run workflow").
#
# Uses GITHUB_TOKEN from the environment or from `.env.release` (see `.env.release.example`).
#
# Optional: RELEASE_TAG=v2.0.1 ./tools/dispatch_github_release.sh  (default: v2.0.0)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env.release" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env.release"
  set +a
fi

: "${GITHUB_TOKEN:?Missing GITHUB_TOKEN. Add it to .env.release (from .env.release.example) or export in the shell.}"
TAG="${RELEASE_TAG:-v2.0.0}"

API="https://api.github.com/repos/lokii-D/lirix/actions/workflows/release.yml/dispatches"
# shellcheck disable=SC2086
curl -fsS -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "$API" \
  -d "{\"ref\":\"main\",\"inputs\":{\"tag\":\"${TAG}\"}}"

echo "[dispatch_github_release] OK — dispatched Release workflow for tag ${TAG} (see Actions tab)."
