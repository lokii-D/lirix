# ADR: Responsibility Boundaries And Dependency Direction


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## Status

Accepted

---

## Context

Lirix has introduced new control-plane modules (`result`, `evidence`, `failure_protocol`, `session`, `forensic_verifier`, `config_authority`) while keeping backward-compatible entrypoints. During the refactor window, the highest risk is cross-layer coupling that silently re-introduces duplicate orchestration and ambiguous ownership.

---

## Decision

- `chain_adapter` is a consumer of resolved config snapshots only. It must not infer fallback behavior that belongs to config authority.
- `evidence` is schema-facing and delegates canonical constructors to `evidence`.
- `failure_protocol` resolves protocol projections; it does not own evidence object construction.
- `forensic_verifier` validates forensic/replay bundles and does not depend on `session` private internals.
- client entrypoints (`validate_only`, `simulate_only`, `validate_and_simulate`) preserve public signatures while converging to shared orchestration paths.

---

## Dependency Direction Contract

- Allowed direction is: entrypoint/client -> core protocols/models -> layers.
- Disallowed direction is any reverse import from core schema/protocol modules back into the client facade (`lirix._facade`, `lirix._client_core` shims).
- Disallowed direction is `chain_adapter` importing config resolution helpers from non-authority modules.

---

## Compatibility Window

- Legacy entrypoints remain additive and forward to canonical implementations.
- Deprecation is announced first as warnings and documentation notes, then removed in a major version only.

---

## Consequences

- Refactors can proceed with contract tests that fail fast on boundary regressions.
- Replay/evidence semantics keep a single canonical source while preserving projection compatibility.
- CI can enforce the architecture baseline before deeper implementation changes.
