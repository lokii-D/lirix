# ADR-0001: Architecture Convergence Baseline and Migration Window


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## Status

Accepted (2026-05-11)

---

## Context

Lirix has accumulated multiple import paths and duplicated runtime fallback behavior:

- Canonical and compatibility entrypoints coexist without a single normative contract.
- Configuration precedence is split across constructor-time and runtime parsing layers.
- CI computes full coverage repeatedly in workflows/matrices.
- Tests are heavily fragmented into single-assertion files, increasing maintenance overhead.

These drifts increase operational risk, make behavior harder to reason about, and slow
developer feedback cycles.

---

## Decision

1. Canonical API authority is the `lirix` root namespace (`Lirix` + stable helpers).
2. `from lirix import Lirix` is the normative surface; `lirix._client_core` remains an
   **internal** re-export / replay-helper package that emits a `DeprecationWarning` on direct
   import (tests may still patch symbols there for parity).
3. Config precedence/fallback authority is centralized in `lirix.core.config_authority`.
4. CI is split into four lanes:
   - Fast Required
   - Coverage Required (single authority runtime)
   - Compatibility Matrix
   - Slow Optional
5. Test topology is reduced by thematic aggregation while preserving assertion parity and
   100% coverage quality bars.

---

## Migration Window and Compatibility Policy

- Window: one minor cycle from introduction of warnings.
- Behavior during window:
  - Compatibility imports continue to function.
  - Warnings are emitted with stable warning categories and remediation text.
  - Documentation and examples only show canonical imports.
- End-of-window policy:
  - Compatibility paths may be hardened behind explicit feature flags or removed in a
    major release.

---

## Baseline Metrics (Frozen)

- Entry surface baseline:
  - Canonical root exports are tracked and gated by root import surface checks.
  - Compatibility entry imports are counted by observability tooling.
- CI baseline:
  - Full-suite + coverage executes exactly once in required checks.
  - Fast lane excludes slow/e2e/network/perf markers.
- Test topology baseline:
  - File count and micro-file ratio are collected by observability tooling.

---

## Consequences

- Positive:
  - Clear usage guidance and safer migration path.
  - Fewer configuration inconsistencies and replay drift risks.
  - Faster required CI with unchanged quality thresholds.
- Trade-offs:
  - Additional warning noise during migration window.
  - Up-front work to consolidate tests and lane routing.
