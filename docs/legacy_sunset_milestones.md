# Legacy Sunset Milestones


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This document defines executable milestones for retiring `lirix.legacy`.

## Scope

- Legacy surface: `lirix.legacy.LirixGuard`
- Canonical replacement: `lirix.Lirix` (`validate_only`, `validate_and_simulate`, async variants)

## Milestones

Milestones are machine-checked by `tools/legacy_sunset_gate.py` via stable IDs.

1. **v1.6.x (current compatibility window)** `id=legacy-window-current`
   - Keep `lirix.legacy` import path available.
   - Emit `DeprecationWarning` on import.
   - No new features land in legacy modules.

2. **v1.7.x (migration enforcement window)** `id=legacy-window-enforcement`
   - Keep behavior stable, but block new legacy-only tests.
   - Require all new examples/integrations to use canonical `Lirix`.
   - Ensure `tests/test_legacy` only verifies adapter compatibility.

3. **v2.0.0 (sunset target)** `id=legacy-window-final`
   - Remove `lirix.legacy` exports from public API.
   - Remove `tests/test_legacy` compatibility-only assertions.
   - Update docs and release notes to finalize migration.

## Exit Conditions

- No production path depends on `LirixGuard`.
- Canonical integration tests fully cover former legacy call shapes.
- Release notes include explicit breaking-change and rollback guidance.

## Automated Validation Path

- `tools/legacy_sunset_gate.py` validates version window and repository shape.
- `tests/test_tools/test_legacy_sunset_gate.py` locks gate behavior in CI.
- At `v1.8.0` and above, `lirix/legacy` and `tests/test_legacy` must both be absent.
