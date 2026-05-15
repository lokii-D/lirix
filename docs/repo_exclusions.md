---
title: Repository exclusions SSOT
purpose: align .gitignore, pytest norecursedirs, audit scope, and harness ignore
---

# Repository exclusions

This file is the **sole SSOT for exclusion boundaries**. `.gitignore` and `.harnessignore` implement Git / local-tooling sync; they must not drift from this document.

**EN:** Keep this document focused on exclusion boundaries only. For general architecture, release, or API contract guidance, use the dedicated docs in `docs/`.
**中文：** 本文档仅负责排除边界；架构、发布与 API 契约请使用 `docs/` 下的专门文档。

## Three-file maintenance rule

When adding or renaming a non-package tree, cache dir, or local-only path:

1. **Document here** — add a row under **Current exclusion set** (and **Scope** if it is a top-level research tree).
2. **`.gitignore`** — add the path if it must never be tracked.
3. **`.harnessignore`** — mirror the same pattern for local harness-style scans.
4. **`pyproject.toml`** → `[tool.pytest.ini_options].norecursedirs` — add the directory name if pytest must not collect there.
5. **`docs/audit_path_map.md`** → Scope / Exclusions — one line if the tree is out of audit scope.

Do not update only one file; CI hygiene and local tooling assume four-way alignment (this doc states intent; the other three enforce it).

## Scope

These paths are out of scope for default package CI, hygiene scanners, and audit tables unless a workflow explicitly targets them.

| Mechanism | Paths / intent |
| --- | --- |
| `.gitignore` | `tdsc/`, `mantle_TT/`, virtualenv dirs (`.venv/`, `.venv*/`, `venv/`, …), local IDE (`.cursor/`), `checklists/`, `prompts/`, … |
| `.harnessignore` | Same local-tooling intent as `.gitignore`; keep in lockstep for top-level research trees and caches |
| `pyproject.toml` → `[tool.pytest.ini_options].norecursedirs` | `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `tdsc`, `mantle_TT` |
| `docs/audit_path_map.md` → Scope / Exclusions | `tdsc/`, `mantle_TT/` called out explicitly |

## Consistency rule

When adding a new non-package research or fork-integration tree:

1. Add it to `.gitignore` if it must never ship as tracked content.
2. Add the directory name to pytest `norecursedirs` if tests must not collect there.
3. Add one line under `docs/audit_path_map.md` Scope / Exclusions.
4. Mirror the same pattern in `.harnessignore`.

## Current exclusion set

### Generated and cache artifacts

`__pycache__/`, `*.py[cod]`, `*.egg-info/`, `.eggs/`, `dist/`, `build/`, `out/`, `cache/`, `.tox/`, `.nox/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `.coverage.*`, `htmlcov/`, `coverage.xml`

### Virtual environments

`.venv/`, `.venv*/`, `venv/`, `env/`, `.venv_ci*/`, `.venv_ci312/`, `.lirix_audit_venv/`, `.lirix_final_preflight_venv/`, `.mantle_tt_venv/`, `_lirix_launch_sandbox/`

### Local-only secrets and machine state

`.env`, `.env.release`, `.DS_Store`, `Thumbs.db`, `node_modules/`, `.cursor/`

### Local research and checklist artifacts

`checklists/`, `prompts/`, `tdsc/`, `mantle_TT/`

### Dev silos and audit artifacts

`.lirix_launch_silo/`, `audit_artifacts/**` except `audit_artifacts/release_signoff/` and `audit_artifacts/release_signoff/**`

## Note

Optional workflows that intentionally enter `mantle_TT/` are documented in `docs/ci_gate_matrix.md`.
