# Mantle Submission One-Pager

## Project

**Lirix** is a security-first AI DevTools pipeline that validates, parses, and policy-audits DeFi transaction intents before execution on Mantle.

## Problem

AI-generated or user-supplied payloads can appear valid while containing unsafe execution patterns:

- missing slippage protection
- recipient poisoning
- router/multicall route poisoning
- proxy-obscured call paths
- inconsistent RPC state views

These failures are expensive and often irreversible on-chain.

## Approach

Lirix applies a layered fail-closed model:

- **L1** intent/payload gate
- **L2** schema and semantic checks
- **L3** DeFi calldata parser (V2/V3/Moe selectors, path checks, multicall recursion guards)
- **L4** RPC quorum consistency verification
- **L5** shadow policy arbitration (`MAX_SLIPPAGE_BPS=50` default)

## Mantle-specific scope delivered

- mainnet/testnet presets (`chain_id` 5000/5001)
- multi-RPC matrix for resilience
- Mantle-focused allowlist addresses
- Multicall3 compatibility
- proxy-aware path handling

## Demonstrated outcome

The bundle shows deterministic rejection of malicious Mantle DeFi payloads and acceptance of safe payloads, with an explicit, test-backed decision path suitable for security-oriented judging.
