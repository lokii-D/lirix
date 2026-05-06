# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixRPCTimeoutException


@pytest.mark.asyncio
async def test_quorum_provider_retry_call_success_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"], retry_attempts=2, retry_base_delay=0.01)
    calls = {"count": 0}

    async def ok():
        calls["count"] += 1
        return "ok"

    assert await provider._retry_call("u1", ok) == "ok"
    assert calls["count"] == 1

    async def bad():
        raise TimeoutError("slow")

    with pytest.raises(LirixRPCTimeoutException):
        await provider._retry_call("u1", bad)
