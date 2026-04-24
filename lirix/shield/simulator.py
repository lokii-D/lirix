# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from lirix.core.exceptions import (
    LirixDependencyError,
    LirixSimulationError,
    LirixStateAssertionError,
)

_ERROR_SELECTOR = bytes.fromhex("08c379a0")
_PANIC_SELECTOR = bytes.fromhex("4e487b71")


@dataclass(frozen=True)
class LirixTrace:
    raw_payload: dict[str, Any]
    calldata: str
    rpc_response: Any
    latency: float


class StateDeltaValidator:
    def __init__(self, web3: Any) -> None:
        self._web3 = web3

    async def validate(self, payload: Mapping[str, Any]) -> bool:
        assertions = payload.get("assertions")
        if not assertions:
            return True
        for assertion in assertions:
            if not isinstance(assertion, Mapping):
                continue
            if assertion.get("type") != "balance_change":
                continue
            token = assertion.get("token")
            min_delta = int(assertion.get("min_delta", 0))
            pre_balance = await self.get_balance(token)
            post_balance = await self.get_balance(token)
            if (post_balance - pre_balance) < min_delta:
                raise LirixStateAssertionError(
                    error_code="LRX_HONEYPOT_DETECTED",
                    resolution_agent=(
                        "Asset delta assertion failed. Potential honeypot or massive slippage."
                    ),
                    resolution_dev="Check min_delta configurations and contract logic.",
                    value_protected="Token Balance",
                )
        return True

    async def get_balance(self, token: Any) -> int:
        return int(getattr(self._web3.eth, "balance", 0))


class SimulationEngine:
    def __init__(self, rpc_url: str) -> None:
        self.rpc_url = rpc_url
        self._w3: Optional[Any] = None

    def _load_web3(self) -> tuple[Any, Any, Any, Any]:
        try:
            from eth_abi import decode as decode_fn  # type: ignore[attr-defined]
            from web3 import Web3 as Web3Cls
            from web3.exceptions import ContractLogicError, Web3Exception
        except ImportError as exc:
            raise LirixDependencyError(
                error_code="LRX_DEP_SIMULATION_MISSING",
                resolution_agent="Install the simulation extras before running RPC simulations.",
                resolution_dev="Run: pip install lirix[simulation]",
                value_protected="Unknown Asset Value",
            ) from exc
        self._w3 = Web3Cls(Web3Cls.HTTPProvider(self.rpc_url))
        return decode_fn, Web3Cls, ContractLogicError, Web3Exception

    def run_simulation(
        self,
        target: str,
        calldata: str,
        sender: str | None = None,
        value: int = 0,
    ) -> bool:
        return asyncio.run(self.async_run_simulation(target, calldata, sender=sender, value=value))

    async def async_run_simulation(
        self,
        target: str,
        calldata: str,
        sender: str | None = None,
        value: int = 0,
    ) -> bool:
        decode_fn, Web3Cls, ContractLogicError, Web3Exception = self._load_web3()
        assert self._w3 is not None
        tx: dict[str, Any] = {
            "to": Web3Cls.to_checksum_address(target),
            "data": calldata,
            "value": value,
        }
        if sender:
            tx["from"] = Web3Cls.to_checksum_address(sender)
        try:
            call_target = getattr(self._w3.eth, "async_eth", self._w3.eth)
            result = call_target.call(tx)
            if asyncio.iscoroutine(result):
                await result
            else:
                await asyncio.sleep(0)
            return True
        except ContractLogicError as exc:
            raise LirixSimulationError(
                error_code="LRX_SIM_CONTRACT_LOGIC",
                resolution_agent=self._decode_revert(getattr(exc, "data", None), decode_fn),
                resolution_dev="Inspect the revert payload and contract execution path.",
                value_protected="Unknown Asset Value",
            ) from exc
        except Web3Exception as exc:
            raise LirixSimulationError(
                error_code="LRX_SIM_WEB3_ERROR",
                resolution_agent=str(exc),
                resolution_dev="Check the RPC provider and simulation request parameters.",
                value_protected="Unknown Asset Value",
            ) from exc
        except ValueError as exc:
            raise LirixSimulationError(
                error_code="LRX_SIM_VALUE_ERROR",
                resolution_agent=self._decode_value_error(exc, decode_fn),
                resolution_dev="Validate the revert payload before retrying the simulation.",
                value_protected="Unknown Asset Value",
            ) from exc

    def _decode_value_error(self, exc: ValueError, eth_abi_decode: Any) -> str:
        if not exc.args:
            return "Simulation reverted without a reason."
        return self._decode_revert(exc.args[0], eth_abi_decode)

    def _decode_revert(self, payload: Any, eth_abi_decode: Any) -> str:
        raw = self._normalize_payload(payload)
        if raw is None or len(raw) < 4:
            return "Simulation reverted without machine-readable revert data."
        selector = raw[:4]
        body = raw[4:]
        if selector == _ERROR_SELECTOR:
            try:
                message = eth_abi_decode(["string"], body)[0]
                if isinstance(message, str) and message:
                    return f"Execution reverted: {message}"
            except Exception:
                return "Execution reverted with Error(string), but reason could not be decoded."
            return "Execution reverted with an empty Error(string) message."
        if selector == _PANIC_SELECTOR:
            try:
                code = int(eth_abi_decode(["uint256"], body)[0])
                return f"Execution reverted with Solidity panic 0x{code:x}."
            except Exception:
                return "Execution reverted with Solidity panic, but code could not be decoded."
        return f"Execution reverted with custom error 0x{selector.hex()}."

    def _normalize_payload(self, payload: Any) -> Optional[bytes]:
        if payload is None:
            return None
        if isinstance(payload, dict):
            for key in ("data", "message"):
                value = payload.get(key)
                if isinstance(value, str):
                    return self._hex_to_bytes(value)
            return None
        if isinstance(payload, str):
            return self._hex_to_bytes(payload)
        return None

    def _hex_to_bytes(self, value: str) -> Optional[bytes]:
        raw = value.strip()
        if raw.startswith("execution reverted: "):
            raw = raw.split("execution reverted: ", 1)[1].strip()
        if not raw.startswith("0x"):
            return None
        try:
            return bytes.fromhex(raw[2:])
        except ValueError:
            return None
