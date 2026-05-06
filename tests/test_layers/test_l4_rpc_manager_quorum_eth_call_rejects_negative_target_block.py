from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixRPCError
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


@pytest.mark.asyncio
async def test_quorum_eth_call_rejects_negative_target_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["http://n1"])

    async def fake_refresh() -> int:
        return 0

    monkeypatch.setattr(provider, "refresh_quorum", fake_refresh)
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        await provider.quorum_eth_call({"to": "0x1"})


@pytest.mark.asyncio
async def test_retry_call_non_retryable_error_raises_directly() -> None:
    provider = AsyncQuorumProvider(["http://n1"])

    async def raise_value_error() -> None:
        raise ValueError("bad payload")

    with pytest.raises(ValueError, match="bad payload"):
        await provider._retry_call("http://n1", raise_value_error)  # noqa: SLF001
