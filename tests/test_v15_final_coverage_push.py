from __future__ import annotations

import asyncio
import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import lirix
import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.integrations.langchain.tool import LirixSecurityValidator
from lirix.layers.l3_proxy_piercer import AbiLRUCache
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_v15_final_coverage_push() -> None:
    config = LirixConfig(chain_id=1, rpc_urls=["https://a.invalid"])
    guardian = Lirix(config=config, rpc_urls=["https://b.invalid", "https://c.invalid"])
    assert guardian.config.rpc_urls == ["https://b.invalid", "https://c.invalid"]


def test_test_v15_final_coverage_push_2() -> None:
    original = sys.version_info
    sys.version_info = (3, 15, 0)  # type: ignore[assignment]
    with pytest.raises(ImportError, match="Python 3.8 through 3.14"):
        importlib.reload(lirix)
    sys.version_info = original  # type: ignore[assignment]
    importlib.reload(lirix)


def test_test_v15_final_coverage_push_3(monkeypatch: pytest.MonkeyPatch) -> None:
    cli_mod = importlib.import_module("lirix.cli")

    class _Parser:
        def parse_args(self, _argv: Any) -> Any:
            return SimpleNamespace(command="unknown")

        def error(self, _message: str) -> None:
            return None

    monkeypatch.setattr(cli_mod, "build_parser", lambda: _Parser())
    assert cli_mod.main(["noop"]) == 2


def test_test_v15_final_coverage_push_4() -> None:
    sys.modules.pop("lirix.cli", None)
    with pytest.raises(SystemExit):
        runpy.run_module("lirix.cli", run_name="__main__")


@pytest.mark.asyncio
async def test_langchain_ainvoke_returns_model_dump_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Model:
        def model_dump_json(self) -> str:
            return '{"ok":true}'

    async def fake_async_validate(
        self: Any, intent: str, payload: dict[str, Any], **kwargs: Any
    ) -> Any:
        return _Model()

    monkeypatch.setattr(Lirix, "async_validate_and_simulate", fake_async_validate)
    validator = LirixSecurityValidator(rpc_urls=["https://rpc.invalid"])
    out = await validator._ainvoke_guardian("payload")
    assert out == '{"ok":true}'


def test_test_v15_final_coverage_push_5(tmp_path: Path) -> None:
    cache = AbiLRUCache(sqlite_path=str(tmp_path / "abi.sqlite3"), invalidation_interval_seconds=1)
    calls = {"count": 0}

    class _StopEvent:
        def __init__(self) -> None:
            self._ticks = 0

        def wait(self, _seconds: int) -> bool:
            self._ticks += 1
            return self._ticks > 1

        def set(self) -> None:
            return None

    cache._stop_event = _StopEvent()  # type: ignore[assignment]
    original = cache._invalidate_stale_locked
    cache._invalidate_stale_locked = lambda: calls.__setitem__("count", calls["count"] + 1)  # type: ignore[method-assign]
    try:
        cache._invalidation_loop()
        assert calls["count"] == 1
    finally:
        cache._invalidate_stale_locked = original  # type: ignore[method-assign]
        cache.close()


@pytest.mark.asyncio
async def test_l4_quorum_eth_call_raises_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["https://node.invalid"])

    async def fake_refresh() -> int:
        return 3

    class _Aw3:
        def __init__(self, _provider: Any) -> None:
            self.eth = SimpleNamespace(call=lambda *_args, **_kwargs: {"ok": True})

        async def is_connected(self) -> bool:
            return False

    monkeypatch.setattr(provider, "refresh_quorum", fake_refresh)
    monkeypatch.setattr("lirix.layers.l4_rpc_manager.AsyncHTTPProvider", lambda url, **kwargs: url)
    monkeypatch.setattr("lirix.layers.l4_rpc_manager.AsyncWeb3", _Aw3)

    with pytest.raises(Exception, match="not connected"):
        await provider.quorum_eth_call({"to": "0x1", "data": "0x"})


def test_test_v15_final_coverage_push_6(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = AsyncQuorumProvider(["https://node.invalid"])
    captured = {"called": False}
    original_run = asyncio.run

    def fake_run(coro: Any) -> Any:
        captured["called"] = True
        return original_run(coro)

    async def fake_quorum_call(_tx: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setattr(asyncio, "run", fake_run)
    monkeypatch.setattr(provider, "quorum_eth_call", fake_quorum_call)
    out = provider.quorum_eth_call_sync({"to": "0x1", "data": "0x"})
    assert captured["called"] is True
    assert out == {"ok": True}
