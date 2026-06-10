# mantle_TT Scripts (SSOT)

All automation for the Mantle submission bundle lives here. Repository-root `scripts/*` entries are thin delegates only.

| Script | Responsibility |
| --- | --- |
| `validate_bundle.sh` | File presence + `type1/to_me.md` symlink SSOT check → prints `bundle-ok` |
| `run_mantle_pytests.sh` | Mantle-focused pytest suite (bundle + `mantle/` tests) |
| `validate_harness.sh` | Full harness: `validate_bundle` + `run_mantle_pytests` + ruff + black |
| `run_mantle_demo.sh` | **Demo launcher** — runs `examples/mantle_defi_demo.py` (canonical) |
| `pack_bundle.sh` | **Packager** — creates `dist/mantle_TT_submission_bundle.tar.gz` |

Recommended order: `validate_bundle` → `run_mantle_pytests` → `run_mantle_demo` → `pack_bundle`, or use root `scripts/full_dry_run.sh` (`validate_harness` + `pack_bundle`).
