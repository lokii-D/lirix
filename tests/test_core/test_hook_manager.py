# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import json
import time
from io import StringIO
from typing import Any, cast

import pytest
from lirix import AuditLogger
from lirix.core.constants import HOOK_LAYER_L2, HOOK_POST_VALIDATE, HOOK_PRE_VALIDATE
from lirix.core.exceptions import (
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    InvalidIntentException,
)
from lirix.core.hook_manager import HookManager


def test_register_hook_and_invoke_sync() -> None:
    mgr = HookManager()
    out: list[int] = []

    def cb(*args: object, **kwargs: object) -> None:
        x = kwargs.get("x", 0)
        assert isinstance(x, int)
        out.append(x)

    mgr.register_hook(HOOK_PRE_VALIDATE, cb)
    assert mgr.invoke_hooks(HOOK_PRE_VALIDATE, x=1) == [None]
    assert out == [1]


def test_register_hook_rejects_bad_signature() -> None:
    mgr = HookManager()

    def bad(x: int) -> int:
        return x

    with pytest.raises(RuntimeError, match="\\*args"):
        mgr.register_hook(HOOK_PRE_VALIDATE, bad)


def test_register_hook_requires_var_kwargs() -> None:
    mgr = HookManager()

    def only_args(*args: object) -> None:
        return None

    with pytest.raises(RuntimeError, match="\\*\\*kwargs"):
        mgr.register_hook(HOOK_PRE_VALIDATE, only_args)


def test_register_hook_requires_var_args() -> None:
    mgr = HookManager()

    def only_kw(**kwargs: object) -> None:
        return None

    with pytest.raises(RuntimeError, match="\\*args"):
        mgr.register_hook(HOOK_PRE_VALIDATE, only_kw)


def test_register_hook_rejects_non_callable() -> None:
    mgr = HookManager()
    bad: object = object()
    with pytest.raises(RuntimeError, match="Unable"):
        mgr.register_hook(HOOK_PRE_VALIDATE, cast(Any, bad))


def test_invoke_unknown_hook_point_raises() -> None:
    mgr = HookManager()
    with pytest.raises(HookUnknownPointException):
        mgr.invoke_hooks("not_a_point")


def test_register_unknown_hook_point_raises() -> None:
    mgr = HookManager()

    def cb(*args: object, **kwargs: object) -> None:
        return None

    with pytest.raises(HookUnknownPointException):
        mgr.register_hook("bad", cb)


def test_invoke_async_hook_with_sync_raises() -> None:
    mgr = HookManager()

    async def acb(*args: object, **kwargs: object) -> int:
        return 1

    mgr.register_hook(HOOK_PRE_VALIDATE, acb)
    with pytest.raises(HookAsyncContextException):
        mgr.invoke_hooks(HOOK_PRE_VALIDATE)


def test_ainvoke_mixed_sync_and_async() -> None:
    mgr = HookManager()

    def s(*args: object, **kwargs: object) -> int:
        x = kwargs["x"]
        assert isinstance(x, int)
        return x + 1

    async def a(*args: object, **kwargs: object) -> int:
        x = kwargs["x"]
        assert isinstance(x, int)
        return x + 2

    mgr.register_hook(HOOK_PRE_VALIDATE, s)
    mgr.register_hook(HOOK_PRE_VALIDATE, a)
    results = asyncio.run(mgr.ainvoke_hooks(HOOK_PRE_VALIDATE, x=1))
    assert results == [2, 3]


def test_ainvoke_unknown_hook_point_raises() -> None:
    mgr = HookManager()
    with pytest.raises(HookUnknownPointException):
        asyncio.run(mgr.ainvoke_hooks("nope"))


def test_hook_execution_exception_wraps() -> None:
    mgr = HookManager()

    def bad(*args: object, **kwargs: object) -> None:
        raise ValueError("boom")

    mgr.register_hook(HOOK_PRE_VALIDATE, bad)
    with pytest.raises(HookExecutionException) as ei:
        mgr.invoke_hooks(HOOK_PRE_VALIDATE)
    assert isinstance(ei.value.__cause__, ValueError)


def test_lirix_security_exception_propagates() -> None:
    mgr = HookManager()

    def bad(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(human_readable_reason="nope")

    mgr.register_hook(HOOK_PRE_VALIDATE, bad)
    with pytest.raises(InvalidIntentException):
        mgr.invoke_hooks(HOOK_PRE_VALIDATE)


def test_ainvoke_wraps_unexpected_errors() -> None:
    mgr = HookManager()

    async def bad(*args: object, **kwargs: object) -> None:
        raise RuntimeError("async boom")

    mgr.register_hook(HOOK_PRE_VALIDATE, bad)
    with pytest.raises(HookExecutionException):
        asyncio.run(mgr.ainvoke_hooks(HOOK_PRE_VALIDATE))


def test_ainvoke_propagates_lirix_exception() -> None:
    mgr = HookManager()

    async def bad(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(human_readable_reason="async nope")

    mgr.register_hook(HOOK_PRE_VALIDATE, bad)
    with pytest.raises(InvalidIntentException):
        asyncio.run(mgr.ainvoke_hooks(HOOK_PRE_VALIDATE))


def test_clear_all_and_single() -> None:
    mgr = HookManager()

    def cb(*args: object, **kwargs: object) -> int:
        return 1

    mgr.register_hook(HOOK_PRE_VALIDATE, cb)
    mgr.clear(HOOK_PRE_VALIDATE)
    assert mgr.invoke_hooks(HOOK_PRE_VALIDATE) == []
    mgr.register_hook(HOOK_PRE_VALIDATE, cb)
    mgr.clear(None)
    assert mgr.invoke_hooks(HOOK_PRE_VALIDATE) == []


def test_clear_missing_hook_no_error() -> None:
    mgr = HookManager()
    mgr.clear(HOOK_PRE_VALIDATE)


def test_invoke_hooks_isolated_lirix_exception_propagates_with_timeout_thread() -> None:
    mgr = HookManager()

    def policy(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(human_readable_reason="blocked in hook")

    mgr.register_hook(HOOK_LAYER_L2, policy)
    with pytest.raises(InvalidIntentException):
        mgr.invoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=1.0)


def test_invoke_hooks_isolated_timeout_without_audit_still_skips() -> None:
    mgr = HookManager()

    def slow(*args: object, **kwargs: object) -> None:
        time.sleep(2.0)

    mgr.register_hook(HOOK_LAYER_L2, slow)
    out = mgr.invoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=0.2)
    assert out[0]["ok"] is False
    assert "timeout" in str(out[0].get("error", ""))


def test_invoke_hooks_isolated_timeout_skips_and_emits_system_audit() -> None:
    buf = StringIO()
    audit = AuditLogger(stream=buf)
    mgr = HookManager()
    mgr.bind_audit_logger(audit)

    def slow(*args: object, **kwargs: object) -> None:
        time.sleep(2.0)

    def after(*args: object, **kwargs: object) -> int:
        return 42

    mgr.register_hook(HOOK_LAYER_L2, slow)
    mgr.register_hook(HOOK_LAYER_L2, after)
    out = mgr.invoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=0.5)
    assert out[0]["ok"] is False
    assert "timeout" in str(out[0].get("error", ""))
    assert out[1]["ok"] is True and out[1].get("result") == 42
    log = buf.getvalue()
    assert "timeout" in log.lower() or "exceeded wall-clock" in log.lower()


def test_invoke_hooks_isolated_suppresses_and_continues() -> None:
    mgr = HookManager()
    log: list[str] = []

    def a(*args: object, **kwargs: object) -> None:
        log.append("a")

    def b(*args: object, **kwargs: object) -> None:
        raise ValueError("x")

    def c(*args: object, **kwargs: object) -> None:
        log.append("c")

    mgr.register_hook(HOOK_LAYER_L2, a)
    mgr.register_hook(HOOK_LAYER_L2, b)
    mgr.register_hook(HOOK_LAYER_L2, c)
    out = mgr.invoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=None)
    assert log == ["a", "c"]
    assert out[0]["ok"] is True
    assert out[1]["ok"] is False
    assert out[2]["ok"] is True


def test_invoke_hooks_isolated_unknown_point_raises() -> None:
    mgr = HookManager()
    with pytest.raises(HookUnknownPointException):
        mgr.invoke_hooks_isolated("not_a_real_point")


def test_ainvoke_hooks_isolated_unknown_point_raises() -> None:
    mgr = HookManager()

    async def _run() -> None:
        await mgr.ainvoke_hooks_isolated("not_a_real_point")

    with pytest.raises(HookUnknownPointException):
        asyncio.run(_run())


def test_ainvoke_hooks_isolated_propagates_lirix_exception() -> None:
    mgr = HookManager()

    async def bad(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(human_readable_reason="async policy")

    mgr.register_hook(HOOK_POST_VALIDATE, bad)
    with pytest.raises(InvalidIntentException):
        asyncio.run(mgr.ainvoke_hooks_isolated(HOOK_POST_VALIDATE))


def test_invoke_hooks_isolated_propagates_lirix_exception() -> None:
    mgr = HookManager()

    def bad(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(human_readable_reason="x")

    mgr.register_hook(HOOK_LAYER_L2, bad)
    with pytest.raises(InvalidIntentException):
        mgr.invoke_hooks_isolated(HOOK_LAYER_L2)


def test_invoke_hooks_isolated_async_cb_records_error() -> None:
    mgr = HookManager()

    async def acb(*args: object, **kwargs: object) -> int:
        return 1

    mgr.register_hook(HOOK_LAYER_L2, acb)
    out = mgr.invoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=None)
    assert out[0]["ok"] is False
    assert out[0].get("error") == "async_hook_requires_ainvoke"


def test_ainvoke_hooks_isolated_sync_callback_timeout_uses_executor() -> None:
    mgr = HookManager()

    def slow_sync(*args: object, **kwargs: object) -> None:
        time.sleep(2.0)

    mgr.register_hook(HOOK_LAYER_L2, slow_sync)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=0.25)

    out = asyncio.run(_run())
    assert out[0]["ok"] is False
    assert "timeout" in str(out[0].get("error", ""))


def test_ainvoke_hooks_isolated_async_timeout_skips() -> None:
    buf = StringIO()
    audit = AuditLogger(stream=buf)
    mgr = HookManager()
    mgr.bind_audit_logger(audit)

    async def slow(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(2.0)

    async def ok(*args: object, **kwargs: object) -> int:
        return 9

    mgr.register_hook(HOOK_LAYER_L2, slow)
    mgr.register_hook(HOOK_LAYER_L2, ok)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_LAYER_L2, timeout_sec=0.5)

    out = asyncio.run(_run())
    assert out[0]["ok"] is False
    assert "timeout" in str(out[0].get("error", ""))
    assert out[1]["ok"] is True


def test_ainvoke_hooks_isolated_async_and_sync() -> None:
    mgr = HookManager()

    async def a(*args: object, **kwargs: object) -> int:
        return 1

    def s(*args: object, **kwargs: object) -> int:
        raise RuntimeError("nope")

    mgr.register_hook(HOOK_LAYER_L2, a)
    mgr.register_hook(HOOK_LAYER_L2, s)
    out = asyncio.run(mgr.ainvoke_hooks_isolated(HOOK_LAYER_L2))
    assert out[0]["ok"] is True
    assert out[1]["ok"] is False


def test_core_package_exports() -> None:
    import lirix.core as core

    assert core.HOOK_PRE_VALIDATE == HOOK_PRE_VALIDATE
    assert core.PREDEFINED_HOOK_POINTS


def test_lirix_public_api_smoke(vitalik_checksum: str) -> None:
    from lirix import Lirix, LirixConfig

    cfg = LirixConfig(chain_id=1, strict_mode=False, rpc_urls=["http://127.0.0.1:8545"])
    client = Lirix(cfg)
    assert client.config.chain_id == 1
    draft = client.audit.new_tx_draft_id()
    buf = StringIO()
    client.audit = AuditLogger(stream=buf)
    client.audit.emit(
        tx_draft_id=draft,
        intent="test.intent",
        blocked_by_layer="none",
        risk_level="low",
        reason="ok",
        context={"to": vitalik_checksum},
        simulation_result=None,
    )
    payload = json.loads(buf.getvalue().strip())
    assert "timestamp" in payload
    assert "Z" in payload["timestamp"]
    assert payload["severity_text"] == "INFO"
    assert "attributes" in payload
