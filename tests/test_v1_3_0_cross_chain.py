from __future__ import annotations

import asyncio
from typing import Any

from _pytest.monkeypatch import MonkeyPatch
from lirix.core.builder import LirixTxBuilder
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider
from lirix.registry.bridges import resolve_bridge_route


def test_async_quorum_provider_routes_to_healthy_node(monkeypatch: MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(
        ["http://stale:8545", "http://timeout:8545", "http://healthy:8545"],
        staleness_threshold=2,
    )

    async def fake_fetch(self: AsyncQuorumProvider, url: str) -> tuple[str, int, float]:
        if "timeout" in url:
            raise TimeoutError("timeout")
        if "stale" in url:
            return url, 100, 0.01
        return url, 105, 0.05

    monkeypatch.setattr(AsyncQuorumProvider, "_fetch_block_number", fake_fetch)

    captured_url: dict[str, str] = {}

    class _FakeEth:
        def __init__(self, url: str) -> None:
            self._url = url

        async def call(
            self, tx: dict[str, str], block_identifier: str = "latest"
        ) -> dict[str, Any]:
            captured_url["url"] = self._url
            return {"ok": tx, "block": block_identifier}

    class _FakeAsyncWeb3:
        def __init__(self, provider_url: str) -> None:
            self.eth = _FakeEth(provider_url)

    monkeypatch.setattr("lirix.layers.l4_rpc_manager.AsyncHTTPProvider", lambda url, **_: url)
    monkeypatch.setattr("lirix.layers.l4_rpc_manager.AsyncWeb3", _FakeAsyncWeb3)

    async def _run() -> None:
        head = await provider.refresh_quorum()
        assert head == 105
        out = await provider.eth_call({"to": "0x0", "data": "0x"})
        assert out["block"] == "latest"

    asyncio.run(_run())
    assert provider.best_url == "http://healthy:8545"
    assert captured_url["url"] == "http://healthy:8545"


def test_bridge_intent_translation_into_l2_payload() -> None:
    draft = LirixTxBuilder().bridge("LayerZero", 1, 137, 100).build()
    route = resolve_bridge_route("LayerZero", 1)

    assert draft["to"] == route.router_address
    assert draft["function_name"] == route.function_name
    assert isinstance(draft["data"], str)
    assert draft["data"].startswith("0x")
