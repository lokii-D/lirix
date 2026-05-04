# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import inspect
import re
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Mapping, NoReturn

from lirix.core.builder import CalldataBuilder
from lirix.core.exceptions import LirixCircuitBreakerError, LirixSimulationError
from lirix.layers import SchemaValidator
from lirix.shield.simulator import LirixTrace, SimulationEngine, StateDeltaValidator


@dataclass(frozen=True)
class _TraceFields:
    raw_payload: dict[str, Any]
    calldata: str
    rpc_response: Any
    latency: float


class LirixGuard:
    def __init__(self, *, rpc_url: str | None = None, debug: bool = False) -> None:
        self.rpc_url = rpc_url
        self.debug = debug
        self._builder = CalldataBuilder()
        self._simulator = SimulationEngine(rpc_url) if rpc_url else None
        self._schema_validator = SchemaValidator()
        self.last_trace: dict[str, Any] | None = None

    @staticmethod
    def _raise_simulation_error(
        error_code: str,
        agent_msg: str,
        dev_msg: str,
    ) -> NoReturn:
        raise LirixSimulationError(
            error_code=error_code,
            resolution_agent=agent_msg,
            resolution_dev=dev_msg,
            value_protected="Unknown Asset Value",
        )

    def parse(self, payload: Mapping[str, Any]) -> bool:
        if inspect.isawaitable(payload):
            self._raise_simulation_error(
                "LRX_SIM_ASYNC_PAYLOAD",
                "Use async_parse for awaitable payload handling.",
                "Pass a concrete mapping payload into parse or async_parse.",
            )
        return asyncio.run(self._parse_impl(payload))

    async def async_parse(self, payload: Mapping[str, Any]) -> bool:
        try:
            return await asyncio.wait_for(self._parse_impl(payload), timeout=5.0)
        except asyncio.TimeoutError:
            raise LirixCircuitBreakerError(
                error_code="LRX_TIMEOUT_BLOCK",
                resolution_agent=("The blockchain RPC did not respond. Abort current transaction."),
                resolution_dev="Check RPC node latency or switch to a fallback provider.",
                value_protected="Unknown Asset Value",
            ) from None

    async def _parse_impl(self, payload: Mapping[str, Any]) -> bool:
        draft = dict(payload)
        self._schema_validator.validate(draft)
        if self.rpc_url:
            target = draft.get("to")
            function_signature = draft.get("function_signature")
            args = draft.get("args", [])
            if not isinstance(target, str):
                self._raise_simulation_error(
                    "LRX_SIM_TARGET_REQUIRED",
                    "Provide a target address for simulation.",
                    "Ensure the payload includes a valid target address.",
                )
            if isinstance(function_signature, str):
                if not isinstance(args, list):
                    self._raise_simulation_error(
                        "LRX_SIM_ARGS_TYPE",
                        "Simulation args must be a list.",
                        "Pass ABI arguments as a list.",
                    )
                calldata = self._builder.build(function_signature, args)
            else:
                data = draft.get("data")
                if not isinstance(data, str):
                    self._raise_simulation_error(
                        "LRX_SIM_SIGNATURE_REQUIRED",
                        "Provide function_signature+args or a prebuilt calldata data field.",
                        "Ensure payload includes either function_signature or data.",
                    )
                calldata = data
            simulator = self._simulator or SimulationEngine(self.rpc_url)
            started = perf_counter()
            rpc_response: Any = None
            try:
                rpc_response = await asyncio.wait_for(
                    simulator.async_run_simulation(
                        target,
                        calldata,
                        sender=draft.get("from"),
                        value=int(draft.get("value", 0)),
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError as exc:
                raise LirixCircuitBreakerError(
                    error_code="LRX_TIMEOUT_BLOCK",
                    resolution_agent=(
                        "The blockchain RPC did not respond. Abort current transaction."
                    ),
                    resolution_dev="Check RPC node latency or switch to a fallback provider.",
                    value_protected="Unknown Asset Value",
                ) from exc
            finally:
                latency = perf_counter() - started
            self.last_trace = self.sanitize_trace(
                asdict(
                    LirixTrace(
                        raw_payload=draft,
                        calldata=calldata,
                        rpc_response=rpc_response,
                        latency=latency,
                    )
                )
            )
            if draft.get("assertions"):
                validator = StateDeltaValidator(getattr(simulator, "_w3", None))
                await validator.validate(draft)
        return True

    def sanitize_trace(self, trace_dict: Mapping[str, Any]) -> dict[str, Any]:
        def _sanitize(value: Any) -> Any:
            if isinstance(value, str):
                return re.sub(r"0x[a-fA-F0-9]{40}", "0x[SANITIZED]", value)
            if isinstance(value, dict):
                return {k: _sanitize(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_sanitize(v) for v in value]
            if isinstance(value, tuple):
                return [_sanitize(v) for v in value]
            return value

        return {key: _sanitize(value) for key, value in trace_dict.items()}
