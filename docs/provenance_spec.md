# Configuration Provenance Specification


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This document defines the canonical semantics for `LirixConfig.config_source_tags`.

## Source Priority

Highest precedence to lowest precedence:

1. `explicit` (user-provided config or explicit rpc override)
2. `profile` (chain profile defaults)
3. `inferred` (chain-level inferred defaults)
4. `runtime` / `runtime_override` (runtime patch overlay)

## Reserved Provenance Fields

- `__provenance_chain__`: ordered stage chain, one of:
  - `inferred>runtime_patch`
  - `explicit>profile>inferred>runtime_patch`
- `__provenance_decisions__`: decision-level source chain, e.g.
  - `config:explicit > defaults:profile_overlay > defaults:l3_inferred > patch:runtime_applied > validate:model`
  - `config:inferred > defaults:l3_inferred > patch:runtime_applied > validate:model`

## Field Value Format

- Key: non-empty string config field name.
- Value: non-empty source token (`explicit`, `profile`, `inferred`, `runtime`, `runtime_override`, `preset`).
- Stable storage: all tags are persisted into `LirixConfig.config_source_tags`.

## Comparison Semantics

- Deterministic comparison is key/value exact equality over normalized string dictionaries.
- Governance snapshots must include `config_source_tags` exactly as resolved by `resolve_config`.
- Any change in source tag values is considered governance-significant and should be tested.
