# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from eth_abi.exceptions import DecodingError
from lirix.core.exceptions import (
    LirixDependencyError,
    LirixSimulationError,
    LirixStateAssertionError,
)
from web3 import Web3

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

    async def validate(
        self,
        payload: Mapping[str, Any],
        simulation_result: Mapping[str, Any] | None = None,
    ) -> bool:
        assertions = payload.get("assertions")
        if not assertions:
            return True

        # Extract simulated return_data (prefer explicit simulation_result, then nested metrics).
        source_data = simulation_result or payload
        raw_return_data = source_data.get("return_data")
        if raw_return_data is None:
            nested_metrics = source_data.get("metrics")
            if isinstance(nested_metrics, Mapping):
                raw_return_data = nested_metrics.get("return_data")
        if raw_return_data is None:
            raw_return_data = "0x"

        # Convert hex return_data into int.
        try:
            actual_int_val = int(raw_return_data, 16) if raw_return_data != "0x" else 0
        except ValueError:
            actual_int_val = 0

        for assertion in assertions:
            # Compatible with Pydantic v2 models or native dicts.
            a_type = getattr(
                assertion,
                "assertion_type",
                assertion.get("assertion_type") if isinstance(assertion, dict) else None,
            )
            e_val = getattr(
                assertion,
                "expected_value",
                assertion.get("expected_value") if isinstance(assertion, dict) else None,
            )

            if a_type == "return_data_int_ge":
                if e_val is None:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion missing expected_value.",
                        resolution_dev="Set expected_value for return_data_int_ge.",
                        value_protected="State Integrity",
                    )
                try:
                    expected_int_val = int(e_val)
                except (TypeError, ValueError) as exc:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion expected_value is not an integer.",
                        resolution_dev='Ensure expected_value is int-like (e.g., 123 or "123").',
                        value_protected="State Integrity",
                    ) from exc

                if actual_int_val < expected_int_val:
                    raise LirixStateAssertionError(
                        error_code="LRX_HONEYPOT_DETECTED",
                        resolution_agent=(
                            f"Return data {actual_int_val} is less than expected "
                            f"{expected_int_val}."
                        ),
                        resolution_dev="Check slippage or state override configurations.",
                        value_protected="State Integrity",
                    )
            elif a_type == "return_data_int_le":
                if e_val is None:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion missing expected_value.",
                        resolution_dev="Set expected_value for return_data_int_le.",
                        value_protected="State Integrity",
                    )
                try:
                    expected_int_val = int(e_val)
                except (TypeError, ValueError) as exc:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion expected_value is not an integer.",
                        resolution_dev='Ensure expected_value is int-like (e.g., 123 or "123").',
                        value_protected="State Integrity",
                    ) from exc

                if actual_int_val > expected_int_val:
                    raise LirixStateAssertionError(
                        error_code="LRX_STATE_MISMATCH",
                        resolution_agent=(
                            f"Return data {actual_int_val} is greater than expected "
                            f"{expected_int_val}."
                        ),
                        resolution_dev=(
                            "Check payout cap assumptions and state override configurations."
                        ),
                        value_protected="State Integrity",
                    )
            elif a_type == "return_data_exact":
                if e_val is None:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion missing expected_value.",
                        resolution_dev="Set expected_value for return_data_exact.",
                        value_protected="State Integrity",
                    )
                try:
                    expected_int_val = int(e_val)
                except (TypeError, ValueError) as exc:
                    raise LirixStateAssertionError(
                        error_code="LRX_ASSERTION_CONFIG_INVALID",
                        resolution_agent="Return-data assertion expected_value is not an integer.",
                        resolution_dev='Ensure expected_value is int-like (e.g., 123 or "123").',
                        value_protected="State Integrity",
                    ) from exc

                if actual_int_val != expected_int_val:
                    raise LirixStateAssertionError(
                        error_code="LRX_STATE_MISMATCH",
                        resolution_agent=(
                            f"Return data {actual_int_val} does not exactly match "
                            f"{expected_int_val}."
                        ),
                        resolution_dev="Ensure exact payload parameters.",
                        value_protected="State Integrity",
                    )
        return True


class SimulationEngine:
    def __init__(self, rpc_url: str) -> None:
        self.rpc_url = rpc_url
        self._w3: Optional[Any] = None

    def _load_web3(self) -> tuple[Any, Any, Any, Any]:
        try:
            from eth_abi import decode as decode_fn  # type: ignore[attr-defined]
            from web3.exceptions import ContractLogicError, Web3Exception
        except ImportError as exc:
            raise LirixDependencyError(
                error_code="LRX_DEP_SIMULATION_MISSING",
                resolution_agent="Install the simulation extras before running RPC simulations.",
                resolution_dev="Run: pip install lirix[simulation]",
                value_protected="Unknown Asset Value",
            ) from exc
        self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        return decode_fn, Web3, ContractLogicError, Web3Exception

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
        try:
            decode_fn, Web3Cls, ContractLogicError, Web3Exception = self._load_web3()
        except ImportError as exc:
            raise LirixDependencyError(
                error_code="LRX_DEP_SIMULATION_MISSING",
                resolution_agent="Install the simulation extras before running RPC simulations.",
                resolution_dev="Run: pip install lirix[simulation]",
                value_protected="Unknown Asset Value",
            ) from exc
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
            except (DecodingError, ValueError, TypeError):
                return "Execution reverted with Error(string), but reason could not be decoded."
            return "Execution reverted with an empty Error(string) message."
        if selector == _PANIC_SELECTOR:
            try:
                code = int(eth_abi_decode(["uint256"], body)[0])
                return f"Execution reverted with Solidity panic 0x{code:x}."
            except (DecodingError, ValueError, TypeError):
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
