# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixRPCTimeoutException


def test_test_l4_rpc_manager_retry_call_timeout_after_elapsed_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"], retry_base_delay=0.01)

    async def bad():
        raise TimeoutError("slow")

    monkeypatch.setattr("lirix.layers.l4_rpc_manager.time.perf_counter", lambda: 0.0)
    with pytest.raises(LirixRPCTimeoutException):
        asyncio.run(provider._retry_call("u1", bad))
