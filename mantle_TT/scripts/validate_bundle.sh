#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

python3 - "$ROOT_DIR" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
required = [
    root / 'README.md',
    root / 'to_me.md',
    root / 'mantle' / 'README.md',
    root / 'mantle' / 'submission_one_pager.md',
    root / 'mantle' / 'architecture.md',
    root / 'mantle' / 'video_script.md',
    root / 'mantle' / 'delivery_checklist.md',
    root / 'mantle' / 'bundle_manifest.md',
    root / 'mantle' / 'final_bundle_index.md',
    root / 'mantle' / 'test_mantle_config.py',
    root / 'demo' / 'mantle_defi_demo.py',
    root / 'docs' / 'submission_one_pager.md',
    root / 'docs' / 'submission_notes.md',
    root / 'docs' / 'video_script.md',
    root / 'docs' / 'delivery_checklist.md',
    root / 'docs' / 'submission_assets' / 'README.md',
    root / 'docs' / 'submission_assets' / '01_hero_banner.png',
    root / 'docs' / 'submission_assets' / '02_malicious_blocked.png',
    root / 'docs' / 'submission_assets' / '03_safe_swap_passed.png',
    root / 'docs' / 'submission_assets' / '04_lirix_2.0.4_core_strengths.png',
    root / 'docs' / 'submission_assets' / '05_final_decision_safe_blocked.png',
    root / 'assets' / 'architecture.md',
    root / 'assets' / 'pitch_outline.md',
    root / 'assets' / 'demo_payload.json',
    root / 'assets' / 'cover.md',
    root / 'scripts' / 'run_mantle_demo.sh',
    root / 'scripts' / 'pack_bundle.sh',
    root / 'scripts' / 'validate_bundle.sh',
    root / 'tests' / 'README.md',
    root / 'tests' / 'mantle' / 'test_mantle_bundle.py',
]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit('Missing files:\n' + '\n'.join(missing))

root_to_me = root / 'to_me.md'
type1_to_me = root / 'type1' / 'to_me.md'
if not type1_to_me.is_symlink():
    raise SystemExit('type1/to_me.md must be a symlink to ../to_me.md (single source of truth).')
link_target = type1_to_me.resolve(strict=True)
if link_target != root_to_me.resolve(strict=True):
    raise SystemExit('type1/to_me.md symlink target must resolve to mantle_TT/to_me.md.')

print('bundle-ok')
PY
