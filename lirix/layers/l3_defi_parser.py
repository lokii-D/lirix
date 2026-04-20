# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Iterable, Optional, Set

from eth_abi import decode as eth_abi_decode  # type: ignore[attr-defined]
from web3 import Web3

from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L3
from lirix.core.exceptions import DeFiSlippageMissingException, MaliciousPayloadException
from lirix.core.hook_manager import HookManager
from lirix.core.signatures import (
    AGGREGATE3_SELECTOR,
    AGGREGATE3_VALUE_SELECTOR,
    MAX_MULTICALL_RECURSION_DEPTH,
    SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
    SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
    SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
)


class DeFiPayloadParser:
    """L3：基于 eth_abi 解析 Uniswap V2 / Multicall3 嵌套 calldata，并做地址黑白名单。"""

    _TYPE_HINTS: dict[str, Any] = {}

    def __init__(self, config: LirixConfig, *, hooks: Optional[HookManager] = None) -> None:
        self._config = config
        self._hooks = hooks

    def _multicall(self) -> str:
        if self._config.multicall3_address:
            return self._config.multicall3_address
        if self._config.chain_id == 1:
            return Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
        raise MaliciousPayloadException(
            human_readable_reason=(
                "chain_id has no built-in Multicall3; configure multicall3_address."
            ),
            context={"layer": "L3", "chain_id": self._config.chain_id},
        )

    def _router(self) -> str:
        if self._config.uniswap_v2_router:
            return self._config.uniswap_v2_router
        if self._config.chain_id == 1:
            return Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
        raise MaliciousPayloadException(
            human_readable_reason=(
                "chain_id has no built-in Uniswap V2 router; configure uniswap_v2_router."
            ),
            context={"layer": "L3", "chain_id": self._config.chain_id},
        )

    def validate(self, payload: dict[str, Any]) -> bool:
        data_raw = payload.get("data")
        if not isinstance(data_raw, str):
            raise MaliciousPayloadException(
                human_readable_reason="data must be a string.",
                context={"layer": "L3"},
            )
        to_raw = payload.get("to")
        if not isinstance(to_raw, str):
            raise MaliciousPayloadException(
                human_readable_reason="to must be a string address.",
                context={"layer": "L3"},
            )
        outer_to = Web3.to_checksum_address(to_raw.strip())
        if data_raw == "0x":
            self._enforce_addresses({outer_to})
            h = self._hooks
            if h is not None:
                h.invoke_hooks_isolated(
                    HOOK_LAYER_L3,
                    layer="L3",
                    payload=payload,
                    timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
                )
            return True
        try:
            blob = bytes.fromhex(data_raw[2:])
        except ValueError as exc:
            raise MaliciousPayloadException(
                human_readable_reason="data is not valid hex.",
                context={"layer": "L3"},
            ) from exc
        if len(blob) < 4:
            self._enforce_addresses({outer_to})
            h = self._hooks
            if h is not None:
                h.invoke_hooks_isolated(
                    HOOK_LAYER_L3,
                    layer="L3",
                    payload=payload,
                    timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
                )
            return True
        sel, body = blob[:4], blob[4:]
        rt = self._router()
        mc = self._multicall()
        swap_selectors = {
            SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
            SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
            SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
        }
        if outer_to == rt and sel not in swap_selectors:
            raise MaliciousPayloadException(
                human_readable_reason="Non-swap calldata directed at Uniswap router.",
                context={"layer": "L3", "selector": sel.hex()},
            )
        if outer_to == mc and sel not in (
            AGGREGATE3_SELECTOR,
            AGGREGATE3_VALUE_SELECTOR,
        ):
            raise MaliciousPayloadException(
                human_readable_reason="Non-aggregate3 calldata directed at Multicall3.",
                context={"layer": "L3", "selector": sel.hex()},
            )
        collected: Set[str] = {outer_to}
        if sel == AGGREGATE3_SELECTOR:
            if outer_to != mc:
                raise MaliciousPayloadException(
                    human_readable_reason=(
                        "aggregate3 calldata must target canonical Multicall3 (route poison)."
                    ),
                    context={
                        "layer": "L3",
                        "outer_to": outer_to,
                        "expected_multicall": mc,
                    },
                )
            self._walk_multicall(body, collected, 0)
        elif sel == AGGREGATE3_VALUE_SELECTOR:
            if outer_to != mc:
                raise MaliciousPayloadException(
                    human_readable_reason=(
                        "aggregate3Value calldata must target canonical Multicall3 (route poison)."
                    ),
                    context={
                        "layer": "L3",
                        "outer_to": outer_to,
                        "expected_multicall": mc,
                    },
                )
            self._walk_multicall_value(body, collected, 0)
        elif sel == SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR:
            if outer_to != rt:
                raise MaliciousPayloadException(
                    human_readable_reason=(
                        "swap calldata must target canonical Uniswap V2 router (route poison)."
                    ),
                    context={
                        "layer": "L3",
                        "outer_to": outer_to,
                        "expected_router": rt,
                    },
                )
            self._accumulate_swap(body, collected, selector=sel)
        self._enforce_addresses(collected)
        h = self._hooks
        if h is not None:
            h.invoke_hooks_isolated(
                HOOK_LAYER_L3,
                layer="L3",
                payload=payload,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return True

    def _walk_multicall(self, body: bytes, collected: Set[str], depth: int) -> None:
        if depth > MAX_MULTICALL_RECURSION_DEPTH:
            raise MaliciousPayloadException(
                human_readable_reason=(
                    "Multicall nesting depth exceeded limit (DoS / stack-safety guard)."
                ),
                context={
                    "layer": "L3",
                    "depth": depth,
                    "max_depth": MAX_MULTICALL_RECURSION_DEPTH,
                },
            )
        mc = self._multicall()
        rt = self._router()
        try:
            decoded = eth_abi_decode(["(address,bool,bytes)[]"], body)
        except Exception as exc:  # noqa: BLE001 — eth_abi 多类型解码错误
            raise MaliciousPayloadException(
                human_readable_reason="Failed to decode Multicall3 aggregate3 arguments.",
                context={"layer": "L3"},
            ) from exc
        calls = decoded[0]
        for target, _allow, cdata in calls:
            taddr = Web3.to_checksum_address(target)
            collected.add(taddr)
            if not cdata:
                continue
            inner_sel = cdata[:4]
            inner_body = cdata[4:]
            if inner_sel == AGGREGATE3_SELECTOR:
                if taddr != mc:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested aggregate3 call must target Multicall3 (Multicall poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._walk_multicall(inner_body, collected, depth + 1)
            elif inner_sel == AGGREGATE3_VALUE_SELECTOR:
                if taddr != mc:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested aggregate3Value call must target Multicall3 "
                            "(Multicall poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._walk_multicall_value(inner_body, collected, depth + 1)
            elif inner_sel in {
                SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
                SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
                SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
            }:
                if taddr != rt:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested swap must target Uniswap V2 router (router poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._accumulate_swap(inner_body, collected, selector=inner_sel)
            else:
                raise MaliciousPayloadException(
                    human_readable_reason="Unsupported inner call inside Multicall3 batch.",
                    context={"layer": "L3", "selector": inner_sel.hex()},
                )

    def _walk_multicall_value(self, body: bytes, collected: Set[str], depth: int) -> None:
        if depth > MAX_MULTICALL_RECURSION_DEPTH:
            raise MaliciousPayloadException(
                human_readable_reason=(
                    "Multicall nesting depth exceeded limit (DoS / stack-safety guard)."
                ),
                context={
                    "layer": "L3",
                    "depth": depth,
                    "max_depth": MAX_MULTICALL_RECURSION_DEPTH,
                },
            )
        mc = self._multicall()
        rt = self._router()
        try:
            decoded = eth_abi_decode(["(address,bool,uint256,bytes)[]"], body)
        except Exception as exc:  # noqa: BLE001
            raise MaliciousPayloadException(
                human_readable_reason="Failed to decode Multicall3 aggregate3Value arguments.",
                context={"layer": "L3"},
            ) from exc
        calls = decoded[0]
        for target, _allow, _wei, cdata in calls:
            taddr = Web3.to_checksum_address(target)
            collected.add(taddr)
            if not cdata:
                continue
            inner_sel = cdata[:4]
            inner_body = cdata[4:]
            if inner_sel == AGGREGATE3_SELECTOR:
                if taddr != mc:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested aggregate3 call must target Multicall3 (Multicall poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._walk_multicall(inner_body, collected, depth + 1)
            elif inner_sel == AGGREGATE3_VALUE_SELECTOR:
                if taddr != mc:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested aggregate3Value call must target Multicall3 "
                            "(Multicall poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._walk_multicall_value(inner_body, collected, depth + 1)
            elif inner_sel in {
                SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
                SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
                SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
            }:
                if taddr != rt:
                    raise MaliciousPayloadException(
                        human_readable_reason=(
                            "Nested swap must target Uniswap V2 router (router poisoning)."
                        ),
                        context={"layer": "L3", "inner_target": taddr},
                    )
                self._accumulate_swap(inner_body, collected, selector=inner_sel)
            else:
                raise MaliciousPayloadException(
                    human_readable_reason="Unsupported inner call inside Multicall3 batch.",
                    context={"layer": "L3", "selector": inner_sel.hex()},
                )

    def _accumulate_swap(self, body: bytes, collected: Set[str], *, selector: bytes) -> None:
        try:
            _a, min_out, path, recipient, _d = eth_abi_decode(
                ["uint256", "uint256", "address[]", "address", "uint256"],
                body,
            )
        except Exception as exc:  # noqa: BLE001
            raise MaliciousPayloadException(
                human_readable_reason="Failed to decode swap calldata.",
                context={"layer": "L3", "selector": selector.hex()},
            ) from exc
        if int(min_out) == 0:
            raise DeFiSlippageMissingException(
                human_readable_reason=(
                    "Swap calldata sets amountOutMin=0; this permits unbounded slippage."
                ),
                context={"layer": "L3", "selector": selector.hex(), "amount_out_min": 0},
            )
        collected.add(Web3.to_checksum_address(recipient))
        for addr in path:
            collected.add(Web3.to_checksum_address(addr))

    def _enforce_addresses(self, addresses: Iterable[str]) -> None:
        addr_set = set(addresses)
        for a in addr_set:
            if a in self._config.blacklisted_addresses:
                raise MaliciousPayloadException(
                    human_readable_reason="Touched address is block-listed.",
                    context={"layer": "L3", "address": a},
                )
        if self._config.whitelisted_addresses:
            for a in addr_set:
                if a not in self._config.whitelisted_addresses:
                    raise MaliciousPayloadException(
                        human_readable_reason="Touched address is not in whitelisted_addresses.",
                        context={"layer": "L3", "address": a},
                    )
