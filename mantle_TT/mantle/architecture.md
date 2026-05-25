# Mantle Submission Architecture

## End-to-end decision flow

```text
Intent + Payload
      |
      v
L1 Intent Gate
      |
      v
L2 Schema/Semantics Gate
      |
      v
L3 DeFi Calldata Parser
  - selector checks
  - route checks
  - recipient/path checks
  - multicall recursion controls
      |
      v
L4 RPC Quorum
  - endpoint health
  - block-height spread control
      |
      v
L5 Shadow Auditor
  - policy overrides
  - slippage threshold
      |
      v
ALLOW / BLOCK (fail-closed)
```

## Mantle-oriented implementation focus

- Preset support for Mantle mainnet/testnet
- Multi-RPC configuration for operational resilience
- Real-address allowlist strategy for routers/tokens
- Multicall3 compatibility and nested-call controls
- Proxy-aware execution inspection paths
