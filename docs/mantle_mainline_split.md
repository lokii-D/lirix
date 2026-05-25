---
title: Mainline vs Mantle harness split
purpose: SSOT for dual-lane responsibilities, paths, and CI ownership
---

# Mainline vs Mantle harness

## Lanes

| Lane | Branch context | Code SSOT | CI workflow | Coverage |
| --- | --- | --- | --- | --- |
| **Mainline** | `main`, feature PRs | `lirix/`, `tests/` (excluding `tests/mantle/`) | `.github/workflows/ci.yml` | **`lirix` 100%** (`fail_under=100`) |
| **Mantle harness** | `mantle-turing-*`, `mantle/**` | `mantle_TT/` | `.github/workflows/mantle-harness-ci.yml` (+ optional `mantle_fork_smoke.yml`) | Harness pytest + bundle gates (not mainline coverage) |

## Rules

1. **Never replace `ci.yml`** with a Mantle-only workflow on `main`.
2. **Do not add `tests/mantle/` or root `app.py`** — duplicates belong under `mantle_TT/`.
3. **`mantle_TT/`** stays in `.gitignore` for default clones; on Mantle branches use `git add -f mantle_TT/` before push so GitHub Actions can read the tree.
4. Mainline **Ruff/Black** run only on `lirix`, `tests`, `tools` (`python tools/harness.py lint` / `format-check`).
5. Mantle **Ruff/Black** run on `mantle_TT/` in `mantle-harness-ci.yml`.

## Local commands

```bash
# Mainline (before merging to main)
python tools/harness.py fast-required-local-chain
python tools/harness.py test-coverage-required

# Mantle harness
bash scripts/mantle/validate_harness.sh
bash mantle_TT/scripts/pack_bundle.sh
```

See also `docs/repo_exclusions.md` and `docs/ci_gate_matrix.md`.
