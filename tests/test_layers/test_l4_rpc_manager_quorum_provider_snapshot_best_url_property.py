# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_quorum_provider_snapshot_best_url_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1", "u2"], staleness_threshold=1)
    provider._best_url = "u1"  # noqa: SLF001
    provider._best_height = 10  # noqa: SLF001
    assert provider.best_url == "u1"
    snap = provider.snapshot()
    assert snap["best_url"] == "u1"


@pytest.mark.asyncio
async def test_quorum_eth_call_refreshes_if_needed(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["u1"], staleness_threshold=1)

    async def fake_refresh(self: AsyncQuorumProvider) -> int:
        self._best_url = "u1"  # noqa: SLF001
        self._best_height = 10  # noqa: SLF001
        return 10

    class _W3:
        def __init__(self) -> None:
            self.eth = self

        async def is_connected(self) -> bool:
            return True

        async def call(self, tx: Any, block_identifier: Any = None) -> str:
            return "ok"

    monkeypatch.setattr(AsyncQuorumProvider, "refresh_quorum", fake_refresh)
    from lirix.layers import l4_rpc_manager as l4

    monkeypatch.setattr(l4, "AsyncWeb3", lambda *args, **kwargs: _W3())
    out = await provider.eth_call({"to": "0x0000000000000000000000000000000000000001"})
    assert out == "ok"
