# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from eth_abi import encode as eth_abi_encode  # type: ignore[attr-defined]
from web3 import Web3

from lirix.core.exceptions import MulticallEncodingException
from lirix.core.signatures import AGGREGATE3_SELECTOR, AGGREGATE3_VALUE_SELECTOR


class MulticallEncoder:
    """Multicall3 原子打包：子调用一律 allowFailure=False（全成全败）；仅产出 calldata，不广播。"""

    def __init__(self, multicall_address: str) -> None:
        self._multicall = Web3.to_checksum_address(multicall_address)

    def encode_transactions(
        self,
        transactions: List[Dict[str, Any]],
        *,
        outer_value_wei: Optional[int] = None,
    ) -> Dict[str, Any]:
        """将多笔子交易编码为单笔对 Multicall3 的调用（aggregate3 / aggregate3Value）。

        每个 dict 需含 ``to``；可选 ``data``（默认 ``0x``）、``value``（wei，默认 0）。
        返回 dict 含 ``to``、``data``、``value``、``access_list``（EIP-2930 空表占位），
        便于 Type-1/2 交易组装。
        """
        if not isinstance(transactions, list) or not transactions:
            raise MulticallEncodingException(
                human_readable_reason="transactions must be a non-empty list.",
                context={"layer": "multicall", "reason": "transactions_empty"},
            )
        parsed: List[Tuple[str, bytes, int]] = []
        for i, raw in enumerate(transactions):
            if not isinstance(raw, dict):
                raise MulticallEncodingException(
                    human_readable_reason="Each transaction must be a dict.",
                    context={"layer": "multicall", "index": i, "reason": "transaction_not_dict"},
                )
            try:
                to_raw = raw["to"]
            except KeyError as exc:
                raise MulticallEncodingException(
                    human_readable_reason="Each transaction must include key 'to'.",
                    context={"layer": "multicall", "index": i, "reason": "missing_to"},
                ) from exc
            if not isinstance(to_raw, str) or not Web3.is_address(to_raw.strip()):
                raise MulticallEncodingException(
                    human_readable_reason="transaction.to must be a valid hex address.",
                    context={
                        "layer": "multicall",
                        "index": i,
                        "to": to_raw,
                        "reason": "invalid_to",
                    },
                )
            to_cs = Web3.to_checksum_address(to_raw.strip())
            data_raw = raw.get("data", "0x")
            if not isinstance(data_raw, str):
                raise MulticallEncodingException(
                    human_readable_reason="transaction.data must be a hex string.",
                    context={"layer": "multicall", "index": i, "reason": "data_not_string"},
                )
            if not data_raw.startswith("0x"):
                raise MulticallEncodingException(
                    human_readable_reason='transaction.data must start with "0x".',
                    context={"layer": "multicall", "index": i, "reason": "data_missing_0x"},
                )
            body_hex = data_raw[2:]
            if len(body_hex) % 2 != 0:
                raise MulticallEncodingException(
                    human_readable_reason="transaction.data hex length must be even.",
                    context={"layer": "multicall", "index": i, "reason": "data_odd_length"},
                )
            try:
                data_b = bytes.fromhex(body_hex) if body_hex else b""
            except ValueError as exc:
                raise MulticallEncodingException(
                    human_readable_reason="transaction.data is not valid hex.",
                    context={"layer": "multicall", "index": i, "reason": "data_invalid_hex"},
                ) from exc
            val = raw.get("value", 0)
            if not isinstance(val, int) or val < 0:
                raise MulticallEncodingException(
                    human_readable_reason="transaction.value must be a non-negative int (wei).",
                    context={"layer": "multicall", "index": i, "reason": "value_invalid"},
                )
            parsed.append((to_cs, data_b, val))

        total_value = sum(v for _, _, v in parsed)
        if outer_value_wei is not None and outer_value_wei != total_value:
            raise MulticallEncodingException(
                human_readable_reason=(
                    "aggregate3Value: declared outer msg.value (wei) must equal "
                    "the sum of per-subcall value fields (fail-closed)."
                ),
                context={
                    "layer": "multicall",
                    "reason": "outer_value_mismatch",
                    "sum_subcall_values_wei": total_value,
                    "outer_value_wei": outer_value_wei,
                },
            )
        if all(v == 0 for _, _, v in parsed):
            calls_abi: List[Tuple[str, bool, bytes]] = [
                (addr, False, cdata) for addr, cdata, _ in parsed
            ]
            try:
                body = eth_abi_encode(["(address,bool,bytes)[]"], [calls_abi])
            except Exception as exc:
                raise MulticallEncodingException(
                    human_readable_reason="ABI encode failed for aggregate3.",
                    context={"layer": "multicall"},
                ) from exc
            selector = AGGREGATE3_SELECTOR
        else:
            calls_val: List[Tuple[str, bool, int, bytes]] = [
                (addr, False, wei, cdata) for addr, cdata, wei in parsed
            ]
            try:
                body = eth_abi_encode(["(address,bool,uint256,bytes)[]"], [calls_val])
            except Exception as exc:
                raise MulticallEncodingException(
                    human_readable_reason="ABI encode failed for aggregate3Value.",
                    context={"layer": "multicall"},
                ) from exc
            selector = AGGREGATE3_VALUE_SELECTOR

        calldata = selector + body
        return {
            "to": self._multicall,
            "data": "0x" + calldata.hex(),
            "value": total_value,
            "access_list": [],
        }
