---
title: Next major hard-removal plan
scope: legacy/signed_only/v2_dual input aliases + related migration scaffolding
status: draft (execution in next major release)
---

**EN:** Next-major removal plan for migration-only aliases; conventions: [`documentation_styleguide.md`](documentation_styleguide.md).<br>
**中文：** 下一主版本硬移除迁移别名的计划；体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## Goal

In the next major release, remove migration-only alias inputs and require single-stack targets:

- `rpc_evidence_mode`: require `v2_only` (remove input acceptance for `legacy` and `v2_dual`)
- `policy_lifecycle_mode`: require `digest_verified` (remove input acceptance for `legacy` and `signed_only`)

This major change is the “hard removal” phase described in `docs/migration_legacy_to_v2.md`.

## Non-goals

- No change to current minor behavior: current releases remain **warn + coerce**.
- No behavioral rollback of the single-stack runtime (already converged).

## Execution checklist (major release PR)

### 1) Input validation: alias removal

- Reject alias labels at config parse/normalization time with a **hard fail**:
  - `ConfigurationGuardException` (or the existing config exception type used for validation failures)
  - Error message must include:
    - the invalid value
    - the required single-stack value
    - a pointer to `docs/migration_legacy_to_v2.md`

### 2) Warning policy: remove migration warnings

- Remove/disable `DeprecationWarning` emissions for the alias inputs (they should no longer be accepted).
- Remove any `filterwarnings` allowances that exist only for alias-input warnings.

### 3) Tests: update migration coverage

- Delete or rewrite tests that assert coercion behavior:
  - Replace “maps to effective mode” assertions with “hard fails on alias inputs”.
- Keep tests that assert single-stack behavior under strict governance (these remain required).

### 4) Docs/examples: remove alias usage

- Update docs/examples to show only:
  - `policy_lifecycle_mode="digest_verified"`
  - `rpc_evidence_mode="v2_only"`
- Ensure “migration state machine” sections move alias inputs from **Migrating** to **Removed**.

### 5) Release notes: major entry

- Add a major-version release note entry:
  - “Removed: alias input acceptance for `legacy`, `v2_dual`, `signed_only`”
  - Clear upgrade instruction (what to change in config)
  - Link back to migration guide

## Verification gates (must pass in major PR)

- `python tools/harness.py contract-manifest`
- `python tools/harness.py root-import-surface`
- `python tools/harness.py test-monkeypatch-convention --strict`
- CI explicit governance gate test list (SSOT: `GOVERNANCE_EXPLICIT_PYTEST_PATHS` in `tools/validators.py`, invoked via `python tools/harness.py test-governance` in `.github/workflows/ci.yml`)
- Full `pytest` suite and closure suites
