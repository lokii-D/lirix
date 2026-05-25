# Mantle Submission Architecture

```text
User / Demo Input
        |
        v
L1 Payload Shape Validation
        |
        v
L2 Semantic Guardrails
        |
        v
L3 DeFi Parser + Router / Multicall Decoding
        |
        v
L4 Multi-RPC Consistency Checks
        |
        v
L5 Shadow Policy Arbitration
        |
        v
Safe / Blocked Decision
```

## Mantle-specific focus

- Mainnet and testnet presets
- Multi-RPC resilience
- Real routers and token contracts
- Proxy-aware DeFi execution paths
