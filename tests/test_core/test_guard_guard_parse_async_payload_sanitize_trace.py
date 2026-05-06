# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix.core.exceptions import LirixCircuitBreakerError, LirixSimulationError
from lirix.core.guard import LirixGuard


def test_test_guard_guard_parse_async_payload_sanitize_trace() -> None:
    guard = LirixGuard()
    pending = asyncio.sleep(0)
    with pytest.raises(LirixSimulationError, match="LRX_SIM_ASYNC_PAYLOAD"):
        guard.parse(pending)  # type: ignore[arg-type]
    pending.close()
    trace = guard.sanitize_trace(
        {
            "addr": "0x0000000000000000000000000000000000000001",
            "nested": ["0x0000000000000000000000000000000000000002"],
        }
    )
    assert trace["addr"] == "0x[SANITIZED]"
    assert trace["nested"][0] == "0x[SANITIZED]"


@pytest.mark.asyncio
async def test_guard_async_timeout_and_signature_required(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = LirixGuard(rpc_url="http://example.invalid")
    monkeypatch.setattr(guard._schema_validator, "validate", lambda draft: True)

    class _Sim:
        async def async_run_simulation(
            self, target: str, calldata: str, sender: Any = None, value: int = 0
        ) -> bool:
            raise asyncio.TimeoutError

    guard._simulator = _Sim()  # noqa: SLF001
    with pytest.raises(LirixCircuitBreakerError, match="LRX_TIMEOUT_BLOCK"):
        await guard.async_parse(
            {
                "to": "0x0000000000000000000000000000000000000001",
                "function_signature": "ping()",
                "args": [],
            }
        )

    with pytest.raises(LirixSimulationError, match="LRX_SIM_SIGNATURE_REQUIRED"):
        await guard._parse_impl({"to": "0x0000000000000000000000000000000000000001"})
