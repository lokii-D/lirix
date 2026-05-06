from __future__ import annotations

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


@pytest.mark.asyncio
async def test_retry_call_zero_retry_budget_hits_unreachable_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"])
    monkeypatch.setattr(provider, "_MAX_RETRIES", 0)

    async def never_called() -> None:
        raise AssertionError("should not be called")

    with pytest.raises(RuntimeError, match="unreachable retry state"):
        await provider._retry_call("u1", never_called)  # noqa: SLF001


@pytest.mark.asyncio
async def test_quorum_eth_call_returns_none_block_hash_without_best_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"])

    async def fake_refresh() -> int:
        # head=2 => target block=1, but deliberately keep _best_url unset
        return 2

    async def fake_retry(url: str, coro_factory):  # type: ignore[no-untyped-def]
        return {"value": 7}

    monkeypatch.setattr(provider, "refresh_quorum", fake_refresh)
    monkeypatch.setattr(provider, "_retry_call", fake_retry)

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})
    assert result["block_hash"] is None
    assert result["winner_url"] == "u1"
    assert result["result"] == {"value": 7}
