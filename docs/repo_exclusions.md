---
title: Repository exclusions SSOT
purpose: align .gitignore, pytest norecursedirs, audit scope, and harness ignore
---

# Repository exclusions (single source of truth)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

These paths are **out of scope** for default Lirix package CI, hygiene scanners, and audit tables unless a workflow explicitly targets them.

| Mechanism | Paths / intent |
| --- | --- |
| `.gitignore` | `tdsc/`, `mantle_TT/`, virtualenv dirs (`.venv/`, `.venv*/`, `venv/`, …), local IDE (`.cursor/`), `checklists/`, `prompts/`, … |
| `pyproject.toml` → `[tool.pytest.ini_options]` `norecursedirs` | `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, **`tdsc`**, **`mantle_TT`** |
| `docs/audit_path_map.md` → Scope / Exclusions | **`tdsc/`**, **`mantle_TT/`** called out explicitly |
| `.harnessignore` (repo root) | Same glob intent as `.gitignore` for local harness-style tooling; keep in sync when adding new top-level research trees |

## Consistency rule

When adding a new **non-package** research or fork-integration tree:

1. Add it to `.gitignore` (if it must never ship in clones as tracked files).
2. Add the directory name to pytest `norecursedirs` if tests must not collect there.
3. Add one line under **`docs/audit_path_map.md`** Scope / Exclusions.
4. Mirror the same pattern in **`.harnessignore`**.

Optional workflows that intentionally enter `mantle_TT/` (e.g. Mantle fork smoke) are documented in `docs/ci_gate_matrix.md`.
