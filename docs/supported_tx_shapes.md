---
title: Supported transaction shapes
purpose: versioned inventory of first-class payload models
compatibility: documentation roadmap; reject or gate unknown shapes in layers
---

# Supported transaction shapes (v1)


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

Lirix L1–L3 today center on **classic externally-owned account (EOA) calldata**:

- Single `to` + `data` (+ optional `value`) payloads.
- **Multicall3** batching via `atomic_multicall` (`aggregate3` / `aggregate3Value`).

## Experimental / not unified in L2–L3

The following are **not** modeled in the same schema core today; callers should treat support as **not declared** unless explicitly extended:

- ERC-4337 `UserOperation` bundles
- EIP-7702 authorization tuples
- Other account-abstraction entrypoints

Future work: extend the DAG with explicit stages and a versioned registry entry per shape—avoid parallel ad-hoc runtimes.
