from __future__ import annotations

import asyncio

from lirix.core.constants import HOOK_POST_VALIDATE, HOOK_PRE_VALIDATE
from lirix.core.evidence import SecurityTrace
from lirix.core.hook_contract import HookPatch
from lirix.core.hook_manager import HookManager
from lirix.core.trace_recorder import TraceRecorder


def test_async_isolated_enforce_mode_rejects_patch_on_post_validate() -> None:
    mgr = HookManager(contract_mode="enforce")
    payload = {"a": 1}

    async def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="should be blocked")

    mgr.register_hook(HOOK_POST_VALIDATE, patcher)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_POST_VALIDATE, payload=payload)

    out = asyncio.run(_run())
    assert out[0]["ok"] is False
    assert out[0]["error_code"] == "LIRIX_HOOK_PATCH_FORBIDDEN"
    assert payload == {"a": 1}


def test_async_isolated_warn_mode_reports_patch_forbidden_warning_on_post_validate() -> None:
    mgr = HookManager(contract_mode="warn")
    payload = {"a": 1}

    async def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="warn only")

    mgr.register_hook(HOOK_POST_VALIDATE, patcher)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_POST_VALIDATE, payload=payload)

    out = asyncio.run(_run())
    assert out[0]["ok"] is True
    assert out[0]["error_code"] == "LIRIX_HOOK_PATCH_FORBIDDEN_WARNING"
    assert out[0].get("patch_allowed") is False
    assert payload == {"a": 1}


def test_async_isolated_shadow_mode_reports_patch_forbidden_shadow_warning_on_post_validate() -> (
    None
):
    mgr = HookManager(contract_mode="shadow")
    payload = {"a": 1}

    async def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="shadow warn")

    mgr.register_hook(HOOK_POST_VALIDATE, patcher)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_POST_VALIDATE, payload=payload)

    out = asyncio.run(_run())
    assert out[0]["ok"] is True
    assert out[0]["error_code"] == "LIRIX_HOOK_PATCH_FORBIDDEN_SHADOW_WARNING"
    assert out[0].get("patch_allowed") is False
    assert payload == {"a": 1}


def test_async_isolated_enforce_mode_applies_patch_on_pre_validate() -> None:
    mgr = HookManager(contract_mode="enforce")
    payload = {"a": 1}

    async def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="enrich")

    mgr.register_hook(HOOK_PRE_VALIDATE, patcher)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload=payload)

    out = asyncio.run(_run())
    assert out[0]["ok"] is True
    assert payload["b"] == 2


def test_async_isolated_records_degraded_trace_when_hook_fails() -> None:
    mgr = HookManager(contract_mode="enforce")
    trace = SecurityTrace.new(correlation_id="c1", intent="swap", payload={"to": "0x1"})
    mgr.bind_trace_recorder(TraceRecorder(trace=trace))
    payload = {"a": 1}

    async def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="blocked")

    mgr.register_hook(HOOK_POST_VALIDATE, patcher)

    async def _run() -> list[dict[str, object]]:
        return await mgr.ainvoke_hooks_isolated(HOOK_POST_VALIDATE, payload=payload)

    out = asyncio.run(_run())
    assert out[0]["ok"] is False
    assert trace.steps[-1].status == "degraded"
