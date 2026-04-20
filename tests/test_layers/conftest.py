# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix.core.signatures import (
    AGGREGATE3_SELECTOR,
    SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
)
from web3 import Web3

SWAP_SELECTOR = SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR


def mainnet_router() -> str:
    return Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")


def mainnet_multicall() -> str:
    return Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")


def token_weth() -> str:
    return Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")


def token_usdc() -> str:
    return Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")


def addr_recipient() -> str:
    return Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")


def malicious_dead() -> str:
    return Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")


def build_swap_calldata(
    *,
    path: list[str],
    recipient: str,
    amount_in: int = 1,
    amount_out_min: int = 1,
    deadline: int = 9_999_999_999,
) -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [amount_in, amount_out_min, path, recipient, deadline],
    )
    return "0x" + SWAP_SELECTOR.hex() + body.hex()


def build_multicall_calldata(calls: list[tuple[str, bool, bytes]]) -> str:
    payload = abi_encode(["(address,bool,bytes)[]"], [calls])
    return "0x" + AGGREGATE3_SELECTOR.hex() + payload.hex()


def stack_nested_multicall(mc_addr: str, wrap_count: int) -> str:
    """将 Multicall3 aggregate3 嵌套 wrap_count 次（用于 DoS / 深度对抗测试）。"""
    cur = build_multicall_calldata([])
    for _ in range(wrap_count):
        inner = bytes.fromhex(cur[2:])
        cur = build_multicall_calldata([(mc_addr, False, inner)])
    return cur
