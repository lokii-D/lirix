# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Union, cast

from eth_abi import decode as eth_abi_decode  # type: ignore[attr-defined]
from web3 import AsyncWeb3, Web3
from web3.exceptions import ContractLogicError, Web3Exception
from web3.types import StateOverride, TxParams

from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L5
from lirix.core.exceptions import (
    ContractPausedException,
    RPCUnavailableException,
    SimulationFailedException,
)
from lirix.core.hook_manager import HookManager

_ERROR_STRING_SELECTOR = bytes.fromhex("08c379a0")
_PANIC_SELECTOR = bytes.fromhex("4e487b71")

_PANIC_REASONS: Dict[int, str] = {
    0x00: "generic compiler-inserted panic.",
    0x01: "assertion failed (assert condition was false).",
    0x11: "arithmetic overflow, underflow, or negative value.",
    0x12: "division or modulo by zero.",
    0x21: "invalid enum conversion.",
    0x22: "incorrectly encoded storage byte array.",
    0x31: "out-of-memory or stack overflow in Yul.",
    0x32: "memory allocation overflow.",
    0x41: "zero-initialized variable of internal function type was called.",
    0x51: "too-large storage array pushed.",
}


def evm_revert_to_natural_language(data: Optional[Union[str, Dict[str, str]]]) -> str:
    raw = _normalize_revert_payload(data)
    if raw is None or len(raw) < 4:
        return "The contract reverted without machine-readable revert data."
    selector = raw[:4]
    body = raw[4:]
    if selector == _ERROR_STRING_SELECTOR:
        return _decode_error_string(body)
    if selector == _PANIC_SELECTOR:
        return _decode_panic(body)
    return (
        "The contract reverted with a custom error "
        f"(selector 0x{selector.hex()}); no standard Error(string)/Panic(uint256) payload."
    )


def _normalize_revert_payload(
    data: Optional[Union[str, Dict[str, str]]],
) -> Optional[bytes]:
    if data is None:
        return None
    if isinstance(data, dict):
        inner = data.get("data") or data.get("message")
        if isinstance(inner, str):
            return _hex_to_bytes(inner)
        return None
    if isinstance(data, str):
        return _hex_to_bytes(data)
    return None


def _hex_to_bytes(h: str) -> Optional[bytes]:
    s = h.strip()
    if not s.startswith("0x"):
        s = "0x" + s
    try:
        return bytes.fromhex(s[2:])
    except ValueError:
        return None


def _decode_error_string(body: bytes) -> str:
    try:
        msg = eth_abi_decode(["string"], body)[0]
        if isinstance(msg, str) and msg:
            return f"Contract reverted with message: {msg}"
        return "Contract reverted with an empty Error(string) message."
    except Exception:  # noqa: BLE001
        return "Contract reverted with Error(string), but the message could not be decoded."


def _decode_panic(body: bytes) -> str:
    try:
        code = int(eth_abi_decode(["uint256"], body)[0])
        detail = _PANIC_REASONS.get(code, f"unknown panic code 0x{code:x}.")
        return f"Solidity panic (0x{code:x}): {detail}"
    except Exception:  # noqa: BLE001
        return "Solidity panic revert; panic code could not be decoded."


def _translate_revert_signature(reason: str) -> Optional[ContractPausedException]:
    lowered = reason.lower()
    if "pausable: paused" in lowered or "blacklisted" in lowered:
        return ContractPausedException(
            human_readable_reason=f"Target contract is paused or restricted: {reason}",
            context={"layer": "L5", "revert_semantics": reason},
        )
    return None


class SandboxSimulator:
    """L5：基于 eth_call 的零 Gas 回滚模拟（不签名、不广播）。"""

    def __init__(self, *, hooks: Optional[HookManager] = None) -> None:
        self._hooks = hooks

    def simulate(
        self,
        payload: Mapping[str, Any],
        *,
        web3: Web3,
        block_number: int,
        state_overrides: Optional[StateOverride] = None,
    ) -> Dict[str, Any]:
        tx = cast(TxParams, self._build_call_tx(payload))
        try:
            if state_overrides is None:
                result = web3.eth.call(tx, block_identifier=block_number)
            else:
                result = web3.eth.call(
                    tx,
                    block_identifier=block_number,
                    state_override=state_overrides,
                )
        except ContractLogicError as exc:
            reason = evm_revert_to_natural_language(exc.data)
            translated = _translate_revert_signature(reason)
            if translated is not None:
                raise translated from exc
            raise SimulationFailedException(
                human_readable_reason=f"Sandbox simulation reverted (zero-Gas eth_call): {reason}",
                context={
                    "layer": "L5",
                    "revert_semantics": reason,
                    "block_number": block_number,
                    "reason": "simulation_reverted",
                },
            ) from exc
        except Web3Exception as exc:
            raise RPCUnavailableException(
                human_readable_reason=f"RPC error during eth_call simulation: {exc!s}",
                context={"layer": "L5", "block_number": block_number, "reason": "rpc_error"},
            ) from exc
        out = self._build_result(block_number=block_number, result=result)
        h = self._hooks
        if h is not None:
            h.invoke_hooks_isolated(
                HOOK_LAYER_L5,
                layer="L5",
                block_number=block_number,
                simulation=out,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return out

    async def simulate_async(
        self,
        payload: Mapping[str, Any],
        *,
        async_web3: AsyncWeb3[Any],
        block_number: int,
        state_overrides: Optional[StateOverride] = None,
    ) -> Dict[str, Any]:
        tx = cast(TxParams, self._build_call_tx(payload))
        try:
            if state_overrides is None:
                result = await async_web3.eth.call(tx, block_identifier=block_number)
            else:
                result = await async_web3.eth.call(
                    tx,
                    block_identifier=block_number,
                    state_override=state_overrides,
                )
        except ContractLogicError as exc:
            reason = evm_revert_to_natural_language(exc.data)
            translated = _translate_revert_signature(reason)
            if translated is not None:
                raise translated from exc
            raise SimulationFailedException(
                human_readable_reason=f"Sandbox simulation reverted (zero-Gas eth_call): {reason}",
                context={
                    "layer": "L5",
                    "revert_semantics": reason,
                    "block_number": block_number,
                    "reason": "simulation_reverted",
                },
            ) from exc
        except Web3Exception as exc:
            raise RPCUnavailableException(
                human_readable_reason=f"RPC error during eth_call simulation: {exc!s}",
                context={"layer": "L5", "block_number": block_number, "reason": "rpc_error"},
            ) from exc
        out = {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x" + result.hex() if result else "0x",
        }
        h = self._hooks
        if h is not None:
            await h.ainvoke_hooks_isolated(
                HOOK_LAYER_L5,
                layer="L5",
                block_number=block_number,
                simulation=out,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return out

    @staticmethod
    def _build_result(*, block_number: int, result: Any) -> Dict[str, Any]:
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x" + result.hex() if result else "0x",
        }

    @staticmethod
    def _build_call_tx(payload: Mapping[str, Any]) -> Dict[str, Any]:
        to_raw = payload.get("to")
        if not isinstance(to_raw, str):
            raise SimulationFailedException(
                human_readable_reason="payload.to is required for simulation.",
                context={"layer": "L5", "reason": "to_missing"},
            )
        data_raw = payload.get("data", "0x")
        if not isinstance(data_raw, str):
            raise SimulationFailedException(
                human_readable_reason="payload.data must be a hex string.",
                context={"layer": "L5", "reason": "data_invalid"},
            )
        value = payload.get("value", 0)
        if not isinstance(value, int):
            raise SimulationFailedException(
                human_readable_reason="payload.value must be an integer wei amount.",
                context={"layer": "L5", "reason": "value_invalid"},
            )
        tx: Dict[str, Any] = {
            "to": Web3.to_checksum_address(to_raw.strip()),
            "data": data_raw,
            "value": value,
        }
        from_raw = payload.get("from")
        if isinstance(from_raw, str) and from_raw.strip():
            tx["from"] = Web3.to_checksum_address(from_raw.strip())
        else:
            tx["from"] = "0x0000000000000000000000000000000000000000"
        return tx
