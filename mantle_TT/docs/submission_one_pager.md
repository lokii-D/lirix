# Mantle Submission One-Pager

## What

Lirix is an AI-assisted DeFi security stack that validates and simulates transaction intent before execution on Mantle.

## Why

Mantle users and builders need a reliable layer that can detect malformed calldata, slippage abuse, router poisoning, and unsafe multicall patterns without slowing down legitimate DeFi workflows.

## How

The pipeline uses layered controls:

- L1 structural validation
- L2 semantic guardrails
- L3 DeFi calldata parsing and proxy-aware routing checks
- L4 multi-RPC consistency validation
- L5 shadow policy arbitration

## Mantle coverage

- Chain presets for mainnet and testnet
- Real router and token allowlists
- Multicall3 support
- V2/V3-style swap selector handling
- Proxy-compatible DeFi execution paths

## Outcome

A malicious Mantle DeFi payload is rejected early, with explicit policy rationale and a reproducible review path.
