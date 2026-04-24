# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, cast

from lirix.core.exceptions import LirixHallucinationError, ValidationFailedException


@dataclass(frozen=True)
class _AbiSignature:
    input_types: tuple[str, ...]
    selector: bytes


class LirixTxBuilder:
    def __init__(self, func_sig: str = "", args: Optional[list[Any]] = None):
        self.func_sig = func_sig
        self.args = list(args or [])
        self._assertions: list[dict[str, Any]] = []
        self._draft_payload: Optional[dict[str, Any]] = None

    def assert_erc20_balance_increase(self, token: str, min_delta: int) -> LirixTxBuilder:
        self._assertions.append({"type": "balance_change", "token": token, "min_delta": min_delta})
        return self

    def build(self) -> dict[str, Any]:
        if self._draft_payload is not None:
            payload = dict(self._draft_payload)
            if self._assertions:
                payload["assertions"] = list(self._assertions)
            return payload
        calldata = CalldataBuilder().build(self.func_sig, self.args)
        built_payload: dict[str, Any] = {"data": calldata}
        if self._assertions:
            built_payload["assertions"] = list(self._assertions)
        return built_payload

    def bridge(
        self,
        protocol: str,
        src_chain: int,
        dst_chain: int,
        amount: int,
    ) -> LirixTxBuilder:
        from lirix.intents.translator import translate_intent

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


class CalldataBuilder:
    def build(self, func_sig: str, args: list[Any]) -> str:
        eth_abi_encode, Web3 = self._load_deps()
        sig = self._parse_signature(func_sig, Web3)
        if len(args) != len(sig.input_types):
            raise ValidationFailedException(
                error_code="LRX_VALIDATION_ARG_COUNT",
                resolution_agent=(
                    "Match the number of calldata arguments to the Solidity signature."
                ),
                resolution_dev=(
                    "Ensure the provided args list length matches the parsed function signature."
                ),
                value_protected="Unknown Asset Value",
            )
        normalized_args = [
            self._validate_arg(typ, arg, Web3) for typ, arg in zip(sig.input_types, args)
        ]
        try:
            encoded_args = eth_abi_encode(list(sig.input_types), normalized_args)
        except Exception as exc:
            raise ValidationFailedException(
                error_code="LRX_VALIDATION_ABI_ENCODE",
                resolution_agent=(
                    "Provide arguments compatible with the declared function signature."
                ),
                resolution_dev="Check ABI types and argument values before encoding.",
                value_protected="Unknown Asset Value",
            ) from exc
        return "0x" + (sig.selector + cast(bytes, encoded_args)).hex()

    def _load_deps(self) -> tuple[Any, Any]:
        try:
            from eth_abi import encode as eth_abi_encode  # type: ignore[attr-defined]
            from web3 import Web3
        except ImportError as exc:
            raise ValidationFailedException(
                error_code="LRX_DEP_SIMULATION_MISSING",
                resolution_agent=(
                    "Install the optional simulation dependencies before building calldata."
                ),
                resolution_dev="Run: pip install lirix[simulation]",
                value_protected="Unknown Asset Value",
            ) from exc
        return eth_abi_encode, Web3

    def _validate_arg(self, typ: str, arg: Any, Web3: Any) -> Any:
        base = typ.rstrip("[]")
        if base == "address" and (not isinstance(arg, str) or not Web3.is_checksum_address(arg)):
            raise LirixHallucinationError(
                error_code="LRX_HALLUCINATION_ADDRESS",
                resolution_agent="Use a valid EIP-55 checksum address.",
                resolution_dev="Reject malformed address arguments before encoding.",
                value_protected="Asset Value",
            )
        return arg

    def _parse_signature(self, func_sig: str, Web3: Any) -> _AbiSignature:
        if not isinstance(func_sig, str) or not func_sig.strip():
            raise ValidationFailedException(
                error_code="LRX_VALIDATION_SIGNATURE_EMPTY",
                resolution_agent="Provide a non-empty Solidity function signature.",
                resolution_dev="Ensure the signature string is present before encoding.",
                value_protected="Unknown Asset Value",
            )
        raw = func_sig.strip()
        if "(" not in raw or not raw.endswith(")"):
            raise ValidationFailedException(
                error_code="LRX_VALIDATION_SIGNATURE_FORMAT",
                resolution_agent=(
                    "Use a canonical Solidity signature like transfer(address,uint256)."
                ),
                resolution_dev=(
                    "Validate function signatures before passing them into the builder."
                ),
                value_protected="Unknown Asset Value",
            )
        _, params = raw.split("(", 1)
        inner = params[:-1].strip()
        input_types = tuple(p.strip() for p in inner.split(",") if p.strip()) if inner else tuple()
        selector_hex = Web3.keccak(text=raw)[:4]
        return _AbiSignature(input_types=input_types, selector=selector_hex)
