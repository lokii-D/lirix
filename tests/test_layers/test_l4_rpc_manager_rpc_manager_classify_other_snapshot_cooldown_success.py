from __future__ import annotations

from typing import Any

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import LirixRPCError
from lirix.layers import l4_rpc_manager as l4
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, RPCManager


def _cfg(urls: list[str]) -> LirixConfig:
    return LirixConfig(chain_id=1, rpc_urls=urls)


def test_test_l4_rpc_manager_rpc_manager_classify_other_snapshot_cooldown_success() -> None:
    mgr = RPCManager(_cfg(["http://a"]))
    classified = mgr._classify_errors({"http://a": RuntimeError("boom")})
    assert classified["other"] == ["http://a"]

    mgr._last_selected_latency = 0.9  # noqa: SLF001
    snapshot = mgr._snapshot_health_locked()  # noqa: SLF001
    assert snapshot["last_selected_latency"] == 0.9

    mgr._failures["http://a"] = 2  # noqa: SLF001
    mgr._open["http://a"] = True  # noqa: SLF001
    mgr._cooldown_until["http://a"] = 10**12  # noqa: SLF001
    mgr._record_transport_success("http://a")  # noqa: SLF001
    assert mgr._failures["http://a"] == 2  # cooldown 未到，状态保持
    assert mgr._open["http://a"] is True


@pytest.mark.asyncio
async def test_async_quorum_provider_failure_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["u1", "u2"], staleness_threshold=0)

    async def all_fail(url: str):
        raise ConnectionError(f"down:{url}")

    monkeypatch.setattr(provider, "_fetch_block_number", all_fail)
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        await provider.refresh_quorum()

    async def all_stale(url: str):
        return (url, 10 if url == "u1" else 5, 0.01)

    provider._staleness_threshold = -1  # noqa: SLF001
    monkeypatch.setattr(provider, "_fetch_block_number", all_stale)
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        await provider.refresh_quorum()


@pytest.mark.asyncio
async def test_async_quorum_eth_call_no_best_and_call_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"])

    async def no_selection() -> int:
        return 0

    monkeypatch.setattr(provider, "refresh_quorum", no_selection)
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        await provider.eth_call({"to": "0x1"})

    provider._best_url = "u1"  # noqa: SLF001

    class _BadW3:
        class eth:
            @staticmethod
            async def call(tx: Any, block_identifier: Any = None) -> Any:
                raise RuntimeError("rpc call failed")

    monkeypatch.setattr(l4, "AsyncWeb3", lambda _provider: _BadW3())
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        await provider.eth_call({"to": "0x1"})


@pytest.mark.asyncio
async def test_async_fetch_block_number_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["u1"])

    class _W3:
        class eth:
            block_number = 1

        async def is_connected(self) -> bool:
            return False

    monkeypatch.setattr(l4, "AsyncWeb3", lambda _provider: _W3())
    with pytest.raises(ConnectionError, match="not connected: u1"):
        await provider._fetch_block_number("u1")  # noqa: SLF001
