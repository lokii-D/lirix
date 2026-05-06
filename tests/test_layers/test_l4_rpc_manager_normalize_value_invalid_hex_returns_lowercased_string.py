from __future__ import annotations

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixRPCTimeoutException


def test_test_l4_rpc_manager_normalize_value_invalid_hex_returns_lowercased_string() -> None:
    normalized = AsyncQuorumProvider._normalize_value({"k": " 0xZZ "})
    assert normalized == {"k": "0xzz"}


@pytest.mark.asyncio
async def test_retry_call_raises_timeout_when_backoff_budget_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = AsyncQuorumProvider(["u1"])
    monkeypatch.setattr(provider, "_MAX_RETRIES", 3)
    monkeypatch.setattr(provider, "_MAX_BACKOFF_TIME_SEC", 0.05)

    ticks = iter([0.00, 0.10])
    monkeypatch.setattr("lirix.layers.l4_rpc_manager.time.perf_counter", lambda: next(ticks, 0.10))

    async def slow() -> None:
        raise TimeoutError("slow node")

    with pytest.raises(
        LirixRPCTimeoutException, match="timed out while waiting for quorum retries"
    ):
        await provider._retry_call("u1", slow)  # noqa: SLF001
