---
title: Assumption register
purpose: trust roots and explicit non-goals bound to Lirix runtime semantics
compatibility: documentation-only; cross-linked from audit_path_map
---

# Assumption register (Lirix 1.6.x)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This register states what Lirix **does not** guarantee and which **trust roots** integrations inherit. It is versioned with the Python package (`lirix.__version__`).

## Trust roots

- **RPC endpoints**: `eth_call` / block data reflect the provider’s view; Lirix does not assert absence of MEV, reorgs, or malicious RPC behavior.
- **Policy bundles**: digest-verified mode enforces SHA-256 integrity of the policy JSON blob only (see `docs/policy_lifecycle_and_rollback.md`); not asymmetric cryptography unless a future mode explicitly adds it.
- **Decoder plugins and chain profiles**: registry contents define the attack surface for calldata interpretation; operators must supply profiles they trust.

## Non-goals

- **Global ordering / mempool safety**: simulation is point-in-time; no ordering guarantees.
- **Cross-node collusion**: quorum logic improves robustness but does not replace a trusted execution model.
- **Hook isolation**: hooks run in-process with timeouts and contracts (`lirix/core/hook_contract.py`); not a kernel or container sandbox.

## Related

- `docs/audit_path_map.md` — code ↔ test ↔ evidence mapping (includes **Harness alignment** terminology: layered gates + GitHub Actions matrix methodology only; **no** external Harness.io SaaS).
- `docs/policy_lifecycle_and_rollback.md` — policy selection and integrity semantics.
