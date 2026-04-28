from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from lirix.layers.l4_rpc_manager import (
    AsyncQuorumProvider,
    LirixConsensusFailureException,
    LirixRPCTimeoutException,
)


class _EthMock:
    def __init__(self, block_number: int, call_result: Any) -> None:
        self._block_number = block_number
        self._call_result = call_result

    @property
    def block_number(self) -> asyncio.Future[int]:
        fut: asyncio.Future[int] = asyncio.Future()
        fut.set_result(self._block_number)
        return fut

    async def call(self, tx: dict[str, Any], block_identifier: Any = None) -> Any:
        return self._call_result

    async def get_block(self, block_number: int) -> Any:
        return type("_Block", (), {"hash": f"block-hash-{block_number}"})()


class _AsyncWeb3Mock:
    def __init__(self, block_number: int, call_result: Any, *, connect: bool = True) -> None:
        self.eth = _EthMock(block_number, call_result)
        self.is_connected = AsyncMock(return_value=connect)


class _FlakyAsyncWeb3Mock(_AsyncWeb3Mock):
    def __init__(self, block_number: int, call_result: Any) -> None:
        super().__init__(block_number, call_result)
        self._call_count = 0

        async def _call(tx: dict[str, Any], block_identifier: Any = None) -> Any:
            self._call_count += 1
            if self._call_count == 1:
                raise ConnectionError("HTTP 429 Too Many Requests")
            return self.eth._call_result

        self.eth.call = _call  # type: ignore[method-assign]


class _HangAsyncWeb3Mock(_AsyncWeb3Mock):
    def __init__(self, block_number: int, call_result: Any) -> None:
        super().__init__(block_number, call_result)

        async def _call(tx: dict[str, Any], block_identifier: Any = None) -> Any:
            raise TimeoutError("node hung")

        self.eth.call = _call  # type: ignore[method-assign]


def _patch_provider_factory(
    monkeypatch: pytest.MonkeyPatch,
    block_numbers: dict[str, int],
    call_results: dict[str, Any],
    *,
    flaky_url: str | None = None,
    hang_url: str | None = None,
) -> None:
    from lirix.layers import l4_rpc_manager as l4

    cache: dict[str, _AsyncWeb3Mock] = {}

    def fake_async_web3(*args: object, **kwargs: object) -> _AsyncWeb3Mock:
        provider = args[0] if args else None
        url = getattr(provider, "endpoint_uri", str(provider))
        if str(url) not in cache:
            if flaky_url is not None and str(url) == flaky_url:
                cache[str(url)] = _FlakyAsyncWeb3Mock(
                    block_numbers[str(url)], call_results[str(url)]
                )
            elif hang_url is not None and str(url) == hang_url:
                cache[str(url)] = _HangAsyncWeb3Mock(
                    block_numbers[str(url)], call_results[str(url)]
                )
            else:
                cache[str(url)] = _AsyncWeb3Mock(block_numbers[str(url)], call_results[str(url)])
        return cache[str(url)]

    monkeypatch.setattr(l4, "AsyncWeb3", fake_async_web3)


@pytest.mark.asyncio  # type: ignore[misc]
async def test_quorum_three_nodes_agree(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 1, "nonce": 7},
        "http://n2": {"balance": 1, "nonce": 7},
        "http://n3": {"balance": 1, "nonce": 7},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["block_number"] == 99
    assert result["result"] == {"balance": 1, "nonce": 7}
    assert len(result["quorum"]) == 3


@pytest.mark.asyncio  # type: ignore[misc]
async def test_quorum_two_nodes_agree_one_malicious(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 10, "nonce": 7},
        "http://n2": {"balance": 10, "nonce": 7},
        "http://n3": {"balance": 999999, "nonce": 7},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["result"] == {"balance": 10, "nonce": 7}
    assert len(result["quorum"]) == 2


@pytest.mark.asyncio  # type: ignore[misc]
async def test_quorum_three_distinct_hashes_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 1},
        "http://n2": {"balance": 2},
        "http://n3": {"balance": 3},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    with pytest.raises(LirixConsensusFailureException):
        await provider.quorum_eth_call({"to": "0x1", "data": "0x"})


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_http_429_backoff_success(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 5},
        "http://n2": {"balance": 5},
        "http://n3": {"balance": 5},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results, flaky_url="http://n1")
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["result"] == {"balance": 5}


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_timeout_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 5},
        "http://n2": {"balance": 5},
        "http://n3": {"balance": 5},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results, hang_url="http://n1")
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    with pytest.raises(LirixRPCTimeoutException):
        await provider.quorum_eth_call({"to": "0x1", "data": "0x"})


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_hex_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": "0x0", "nonce": 7},
        "http://n2": {"nonce": 7, "balance": "0x"},
        "http://n3": {"balance": "0x000", "nonce": 7},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["result"] == {"balance": "0x0", "nonce": 7}


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_block_hash_reflected_in_result(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100, "http://n3": 100}
    call_results = {
        "http://n1": {"balance": 1},
        "http://n2": {"balance": 1},
        "http://n3": {"balance": 1},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["block_hash"] == "block-hash-99"


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_two_nodes_require_unanimous_quorum(monkeypatch: pytest.MonkeyPatch) -> None:
    block_numbers = {"http://n1": 100, "http://n2": 100}
    call_results = {"http://n1": {"balance": 1}, "http://n2": {"balance": 1}}
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["result"] == {"balance": 1}
    assert len(result["quorum"]) == 2


@pytest.mark.asyncio  # type: ignore[misc]
async def test_bft_four_nodes_require_dynamic_three_vote_quorum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    block_numbers = {
        "http://n1": 100,
        "http://n2": 100,
        "http://n3": 100,
        "http://n4": 100,
    }
    call_results = {
        "http://n1": {"balance": 42},
        "http://n2": {"balance": 42},
        "http://n3": {"balance": 42},
        "http://n4": {"balance": 99},
    }
    _patch_provider_factory(monkeypatch, block_numbers, call_results)
    provider = AsyncQuorumProvider(["http://n1", "http://n2", "http://n3", "http://n4"])

    result = await provider.quorum_eth_call({"to": "0x1", "data": "0x"})

    assert result["result"] == {"balance": 42}
    assert len(result["quorum"]) == 3
