# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from types import MappingProxyType
from typing import Final, FrozenSet, Mapping

# --- Multicall3 / 聚合 ---
AGGREGATE3_SELECTOR: Final[bytes] = bytes.fromhex("82ad56cb")
AGGREGATE3_VALUE_SELECTOR: Final[bytes] = bytes.fromhex("174dea71")

# --- Uniswap V2 Router 常见 swap 入口 ---
SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR: Final[bytes] = bytes.fromhex("38ed1739")
SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR: Final[bytes] = bytes.fromhex("7ff36ab5")
SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR: Final[bytes] = bytes.fromhex("18cbafe5")

# --- ERC20 标准 ---
ERC20_TRANSFER_SELECTOR: Final[bytes] = bytes.fromhex("a9059cbb")
ERC20_APPROVE_SELECTOR: Final[bytes] = bytes.fromhex("095ea7b3")

# --- Uniswap V2 Multicall（multicall(bytes[])，常见于路由批量）---
UNISWAP_MULTICALL_AGGREGATE_SELECTOR: Final[bytes] = bytes.fromhex("5ae401dc")

# --- L3：嵌套 Multicall 递归上限（防 Zip-bomb / 栈耗尽 DoS）---
MAX_MULTICALL_RECURSION_DEPTH: Final[int] = 5

# --- L2：calldata 十六进制串最大长度（含 "0x"），防内存耗尽 ---
MAX_L2_CALLDATA_HEX_CHARS: Final[int] = 32768

# --- EVM uint256 上界（含）---
UINT256_MAX: Final[int] = 2**256 - 1

SWAP_INTENT_ALLOWED_SELECTORS: Final[FrozenSet[bytes]] = frozenset(
    {
        SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
        SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
        SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
        AGGREGATE3_SELECTOR,
        AGGREGATE3_VALUE_SELECTOR,
    }
)

TRANSFER_INTENT_ALLOWED_SELECTORS: Final[FrozenSet[bytes]] = frozenset({ERC20_TRANSFER_SELECTOR})

INTENT_TO_ALLOWED_SELECTORS: Final[Mapping[str, FrozenSet[bytes]]] = MappingProxyType(
    {
        "swap": SWAP_INTENT_ALLOWED_SELECTORS,
        "transfer": TRANSFER_INTENT_ALLOWED_SELECTORS,
    }
)

FUNCTION_NAME_TO_ALLOWED_SELECTORS: Final[Mapping[str, FrozenSet[bytes]]] = MappingProxyType(
    {
        "swapExactTokensForTokens": frozenset({SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR}),
        "swapExactETHForTokens": frozenset({SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR}),
        "swapExactTokensForETH": frozenset({SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR}),
        "transfer": frozenset({ERC20_TRANSFER_SELECTOR}),
        "approve": frozenset({ERC20_APPROVE_SELECTOR}),
        "aggregate3": frozenset({AGGREGATE3_SELECTOR}),
        "aggregate3Value": frozenset({AGGREGATE3_VALUE_SELECTOR}),
    }
)
