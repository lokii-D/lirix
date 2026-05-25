#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/dist"
ARCHIVE="$OUT_DIR/mantle_TT_submission_bundle.tar.gz"
mkdir -p "$OUT_DIR"

FILES=(
  README.md
  to_me.md
  app.py
  Dockerfile
  docker-compose.yml
  contracts
  assets
  demo
  docs
  examples
  mantle
  scripts
  tests
)

tar -czf "$ARCHIVE" -C "$ROOT_DIR" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.DS_Store' \
  "${FILES[@]}"

echo "$ARCHIVE"
