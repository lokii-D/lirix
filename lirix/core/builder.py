# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Optional

from lirix.core.calldata_builder import CalldataBuilder
from lirix.intents.translator import translate_intent


class LirixTxBuilder:
    def __init__(self, func_sig: str = "", args: Optional[list[Any]] = None):
        self.func_sig = func_sig
        self.args = list(args or [])
        self._assertions: list[dict[str, Any]] = []
        self._draft_payload: Optional[dict[str, Any]] = None

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if (
            "data" in payload
            and isinstance(payload["data"], str)
            and payload["data"].startswith("0X")
        ):
            payload["data"] = "0x" + payload["data"][2:]
        return payload

    def assert_erc20_balance_increase(self, token: str, min_delta: int) -> LirixTxBuilder:
        # L5 validates math against simulated `return_data`, so token is currently not used.
        self._assertions.append(
            {"assertion_type": "return_data_int_ge", "expected_value": min_delta}
        )
        return self

    def build(self) -> dict[str, Any]:
        if self._draft_payload is not None:
            payload = self._normalize_payload(dict(self._draft_payload))
            if self._assertions:
                payload["assertions"] = [dict(item) for item in self._assertions]
            return payload
        calldata = CalldataBuilder().build(self.func_sig, self.args)
        built_payload: dict[str, Any] = {"data": calldata}
        if self._assertions:
            built_payload["assertions"] = [dict(item) for item in self._assertions]
        return self._normalize_payload(built_payload)

    def bridge(
        self,
        protocol: str,
        src_chain: int,
        dst_chain: int,
        amount: int,
    ) -> LirixTxBuilder:
        self._draft_payload = translate_intent(
            {
                "type": "bridge",
                "protocol": protocol,
                "src_chain": src_chain,
                "dst_chain": dst_chain,
                "amount": amount,
            }
        )
        return self


__all__ = ["CalldataBuilder", "LirixTxBuilder"]
