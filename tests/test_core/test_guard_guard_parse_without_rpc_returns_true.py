# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix.core.exceptions import LirixCircuitBreakerError, LirixSimulationError
from lirix.core.guard import LirixGuard


def test_parse_without_rpc_returns_true_for_basic_payload() -> None:
    guard = LirixGuard()
    assert (
        guard.parse(
            {
                "to": "0x0000000000000000000000000000000000000001",
                "function_name": "transfer",
                "data": "0x",
            }
        )
        is True
    )


def test_async_parse_wraps_timeout_as_circuit_breaker(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = LirixGuard()

    async def _raise_timeout(*args: Any, **kwargs: Any) -> bool:
        raise asyncio.TimeoutError()

    monkeypatch.setattr(guard, "_parse_impl", _raise_timeout)
    with pytest.raises(LirixCircuitBreakerError, match="LRX_TIMEOUT_BLOCK"):
        asyncio.run(
            guard.async_parse({"to": "0x0000000000000000000000000000000000000001", "data": "0x"})
        )


def test_parse_rejects_awaitable_payload_with_simulation_error() -> None:
    guard = LirixGuard()

    class _AwaitablePayload:
        def __await__(self):
            async def _inner() -> dict[str, str]:
                return {"to": "0x0", "data": "0x"}

            return _inner().__await__()

    with pytest.raises(LirixSimulationError, match="LRX_SIM_ASYNC_PAYLOAD"):
        guard.parse(_AwaitablePayload())
