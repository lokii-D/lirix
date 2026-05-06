# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixRPCTimeoutException, RPCManager


def _cfg(urls: list[str]) -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=urls,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def test_test_rpc_manager_classify_health_context() -> None:
    mgr = RPCManager(_cfg(["http://a", "http://b"]))
    ctx = mgr._health_context()
    assert ctx["rpc_urls"] == ["http://a", "http://b"]
    assert mgr._classify_errors({"a": ConnectionError("x"), "b": TimeoutError("x")})[
        "transport"
    ] == ["a"]


@pytest.mark.asyncio
async def test_async_quorum_provider_refresh_and_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["http://a", "http://b"])

    async def fake_fetch(self: Any, url: str) -> tuple[str, int, float]:
        return url, 10 if url.endswith("a") else 9, 0.1

    monkeypatch.setattr(AsyncQuorumProvider, "_fetch_block_number", fake_fetch)
    assert await provider.refresh_quorum() == 10
    assert provider.best_url == "http://a"
    assert provider._hash_result({"a": "0x1"}) == provider._hash_result({"a": 1})


@pytest.mark.asyncio
async def test_retry_call_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["http://a"], retry_attempts=1, retry_base_delay=0.0)

    async def coro() -> Any:
        raise TimeoutError("slow")

    with pytest.raises(LirixRPCTimeoutException):
        await provider._retry_call("http://a", coro)
