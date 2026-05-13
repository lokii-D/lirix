# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_LAYER_L4
from lirix.core.exceptions import (
    CircuitBreakerOpenException,
    RPCQuotaExhaustedException,
    RPCUnavailableException,
)
from lirix.core.hook_manager import HookManager
from lirix.layers.l4_rpc_manager import BLOCK_HEIGHT_SPREAD_THRESHOLD, RPCManager
from tests.conftest import RPC_URL_TINY_PORT


def _cfg(urls: list[str]) -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=urls,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def test_test_l4_rpc_manager() -> None:
    mgr = RPCManager(_cfg([]))
    with pytest.raises(RPCUnavailableException) as ei:
        mgr.sync_reconcile()
    assert ei.value.context.get("reason") == "rpc_urls_empty"


def test_test_l4_rpc_manager_2() -> None:
    mgr = RPCManager(_cfg([RPC_URL_TINY_PORT]))
    with pytest.raises(RPCUnavailableException) as ei:
        mgr.sync_web3()
    assert ei.value.context.get("reason") == "web3_not_ready"


def test_test_l4_rpc_manager_3(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://good:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        return url, 42

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    assert mgr.sync_reconcile() == 42
    assert mgr.sync_web3() is not None


def test_test_l4_rpc_manager_4(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://good:8545"])
    hooks = HookManager()
    modes: list[str] = []

    def on_l4(*args: object, **kwargs: object) -> None:
        m = kwargs.get("mode")
        if isinstance(m, str):
            modes.append(m)

    hooks.register_hook(HOOK_LAYER_L4, on_l4)
    mgr = RPCManager(cfg, hooks=hooks)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        return url, 3

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    assert mgr.sync_reconcile() == 3
    assert modes == ["sync"]


def test_test_l4_rpc_manager_5(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://async-hook:8545"])
    hooks = HookManager()
    modes: list[str] = []

    def on_l4(*args: object, **kwargs: object) -> None:
        m = kwargs.get("mode")
        if isinstance(m, str):
            modes.append(m)

    hooks.register_hook(HOOK_LAYER_L4, on_l4)
    mgr = RPCManager(cfg, hooks=hooks)

    async def fake_async(self: RPCManager, url: str) -> tuple[str, int]:
        return url, 8

    monkeypatch.setattr(RPCManager, "_fetch_block_number_async", fake_async)

    async def _run() -> int:
        return await mgr.async_reconcile()

    assert asyncio.run(_run()) == 8
    assert modes == ["async"]


def test_test_l4_rpc_manager_6(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://a:8545", "http://b:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        if "a" in url:
            return url, 100
        return url, 100 + BLOCK_HEIGHT_SPREAD_THRESHOLD + 1

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    with pytest.raises(RPCUnavailableException) as ei:
        mgr.sync_reconcile()
    assert ei.value.context.get("spread") is not None


def test_test_l4_rpc_manager_7(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = RPCManager(_cfg(["http://quota:8545"]))
    before_failures = dict(mgr._failures)  # noqa: SLF001

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        raise ConnectionError("HTTP 429 Too Many Requests")

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    with pytest.raises(RPCQuotaExhaustedException):
        mgr.sync_reconcile()
    assert mgr._failures == before_failures  # noqa: SLF001


def test_test_l4_rpc_manager_8(monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = RPCManager(_cfg(["http://quota-async:8545"]))
    before_failures = dict(mgr._failures)  # noqa: SLF001

    async def fake_async(self: RPCManager, url: str) -> tuple[str, int]:
        raise ConnectionError("Too Many Requests")

    monkeypatch.setattr(RPCManager, "_fetch_block_number_async", fake_async)

    async def _run() -> None:
        await mgr.async_reconcile()

    with pytest.raises(RPCQuotaExhaustedException):
        asyncio.run(_run())
    assert mgr._failures == before_failures  # noqa: SLF001


def test_test_l4_rpc_manager_9(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _cfg(["http://unreachable:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        raise ConnectionError("transport down")

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    for _ in range(3):
        with pytest.raises(RPCUnavailableException):
            mgr.sync_reconcile()
    with pytest.raises(CircuitBreakerOpenException):
        mgr.sync_reconcile()


def test_test_l4_rpc_manager_10(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://unreachable:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        raise ConnectionError("transport down")

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    for _ in range(3):
        with pytest.raises(RPCUnavailableException):
            mgr.sync_reconcile()
    mgr.reset_circuit_breakers()
    assert mgr._open.get("http://unreachable:8545") is not True  # noqa: SLF001


def test_test_l4_rpc_manager_11(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://a:8545", "http://b:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        if "a" in url:
            return url, 10
        raise ConnectionError("down")

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    with pytest.raises(RPCUnavailableException) as ei:
        mgr.sync_reconcile()
    assert ei.value.context.get("ok_count") == 1


def test_test_l4_rpc_manager_12(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://async:8545"])
    mgr = RPCManager(cfg)

    async def fake_async(self: RPCManager, url: str) -> tuple[str, int]:
        return url, 7

    monkeypatch.setattr(RPCManager, "_fetch_block_number_async", fake_async)

    async def _run() -> int:
        return await mgr.async_reconcile()

    assert asyncio.run(_run()) == 7
    assert mgr.async_web3() is not None


def test_test_l4_rpc_manager_13() -> None:
    mgr = RPCManager(_cfg(["http://x:8545"]))
    with pytest.raises(RPCUnavailableException) as ei:
        mgr.async_web3()
    assert ei.value.context.get("reason") == "async_web3_not_ready"


def test_test_l4_rpc_manager_14(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://n1:8545", "http://n2:8545", "http://n3:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        return url, 5

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    assert mgr.sync_reconcile() == 5


def test_test_l4_rpc_manager_15(monkeypatch: pytest.MonkeyPatch) -> None:
    from lirix.layers import l4_rpc_manager as l4

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    mock_w3.eth.block_number = 99
    monkeypatch.setattr(l4, "Web3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://ok:8545"]))
    assert mgr._fetch_block_number_sync("http://ok:8545") == ("http://ok:8545", 99)


def test_test_l4_rpc_manager_16(monkeypatch: pytest.MonkeyPatch) -> None:
    from lirix.layers import l4_rpc_manager as l4

    class _Eth:
        @property
        def block_number(self) -> asyncio.Future[int]:
            fut: asyncio.Future[int] = asyncio.Future()
            fut.set_result(55)
            return fut

    mock_w3 = MagicMock()
    mock_w3.is_connected = AsyncMock(return_value=True)
    mock_w3.eth = _Eth()
    monkeypatch.setattr(l4, "AsyncWeb3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://ok-async:8545"]))

    async def _run() -> tuple[str, int]:
        return await mgr._fetch_block_number_async("http://ok-async:8545")

    assert asyncio.run(_run()) == ("http://ok-async:8545", 55)


def test_test_l4_rpc_manager_17(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix.layers import l4_rpc_manager as l4

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    type(mock_w3.eth).block_number = PropertyMock(
        side_effect=ConnectionError("HTTP 429 Too Many Requests")
    )
    monkeypatch.setattr(l4, "Web3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://quota-inner:8545"]))
    with pytest.raises(RPCQuotaExhaustedException):
        mgr._fetch_block_number_sync("http://quota-inner:8545")


def test_test_l4_rpc_manager_18(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix.layers import l4_rpc_manager as l4

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = True
    type(mock_w3.eth).block_number = PropertyMock(side_effect=ConnectionError("transport down"))
    monkeypatch.setattr(l4, "Web3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://sync-transport-err:8545"]))
    with pytest.raises(ConnectionError, match="transport down"):
        mgr._fetch_block_number_sync("http://sync-transport-err:8545")


def test_test_l4_rpc_manager_19(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix.layers import l4_rpc_manager as l4

    class _Eth:
        @property
        def block_number(self) -> asyncio.Future[int]:
            fut: asyncio.Future[int] = asyncio.Future()
            fut.set_exception(ConnectionError("Too Many Requests"))
            return fut

    mock_w3 = MagicMock()
    mock_w3.is_connected = AsyncMock(return_value=True)
    mock_w3.eth = _Eth()
    monkeypatch.setattr(l4, "AsyncWeb3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://quota-inner-async:8545"]))

    async def _run() -> None:
        await mgr._fetch_block_number_async("http://quota-inner-async:8545")

    with pytest.raises(RPCQuotaExhaustedException):
        asyncio.run(_run())


def test_test_l4_rpc_manager_20(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix.layers import l4_rpc_manager as l4

    class _Eth:
        @property
        def block_number(self) -> asyncio.Future[int]:
            fut: asyncio.Future[int] = asyncio.Future()
            fut.set_exception(ConnectionError("transport down"))
            return fut

    mock_w3 = MagicMock()
    mock_w3.is_connected = AsyncMock(return_value=True)
    mock_w3.eth = _Eth()
    monkeypatch.setattr(l4, "AsyncWeb3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://async-transport-err:8545"]))

    async def _run() -> None:
        await mgr._fetch_block_number_async("http://async-transport-err:8545")

    with pytest.raises(ConnectionError, match="transport down"):
        asyncio.run(_run())


def test_test_l4_rpc_manager_21(monkeypatch: pytest.MonkeyPatch) -> None:
    from lirix.layers import l4_rpc_manager as l4

    mock_w3 = MagicMock()
    mock_w3.is_connected.return_value = False
    mock_w3.eth.block_number = 1
    monkeypatch.setattr(l4, "Web3", lambda *a, **kw: mock_w3)
    mgr = RPCManager(_cfg(["http://x:8545"]))
    with pytest.raises(ConnectionError, match="not connected"):
        mgr._fetch_block_number_sync("http://x:8545")


def test_test_l4_rpc_manager_22(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://bad:8545", "http://good:8545"])
    mgr = RPCManager(cfg)

    async def fake_async(self: RPCManager, url: str) -> tuple[str, int]:
        if "bad" in url:
            raise ConnectionError("down")
        return url, 1

    monkeypatch.setattr(RPCManager, "_fetch_block_number_async", fake_async)

    async def _run() -> None:
        await mgr.async_reconcile()

    with pytest.raises(RPCUnavailableException):
        asyncio.run(_run())


def test_test_l4_rpc_manager_23(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://a:8545", "http://b:8545"])
    mgr = RPCManager(cfg)

    async def fake_async(self: RPCManager, url: str) -> tuple[str, int]:
        if "a" in url:
            return url, 100
        return url, 100 + BLOCK_HEIGHT_SPREAD_THRESHOLD + 1

    monkeypatch.setattr(RPCManager, "_fetch_block_number_async", fake_async)

    async def _run() -> None:
        await mgr.async_reconcile()

    with pytest.raises(RPCUnavailableException) as ei:
        asyncio.run(_run())
    assert ei.value.context.get("spread") is not None


def test_test_l4_rpc_manager_24(monkeypatch: pytest.MonkeyPatch) -> None:
    from lirix.layers import l4_rpc_manager as l4

    mock_w3 = MagicMock()
    mock_w3.is_connected = AsyncMock(return_value=False)

    def _fake_async_w3(*_a: object, **_k: object) -> MagicMock:
        return mock_w3

    monkeypatch.setattr(l4, "AsyncWeb3", _fake_async_w3)
    mgr = RPCManager(_cfg(["http://async-bad:8545"]))

    async def _run() -> None:
        await mgr._fetch_block_number_async("http://async-bad:8545")

    with pytest.raises(ConnectionError):
        asyncio.run(_run())


def test_test_l4_rpc_manager_25(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg(["http://bad:8545", "http://good:8545"])
    mgr = RPCManager(cfg)

    def fake_fetch(self: RPCManager, url: str) -> tuple[str, int]:
        if "bad" in url:
            raise ConnectionError("down")
        return url, 123

    monkeypatch.setattr(RPCManager, "_fetch_block_number_sync", fake_fetch)
    for _ in range(3):
        with pytest.raises(RPCUnavailableException):
            mgr.sync_reconcile()
    assert mgr.sync_reconcile() == 123
