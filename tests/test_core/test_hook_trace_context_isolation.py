from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from lirix.core.constants import HOOK_PRE_VALIDATE
from lirix.core.evidence import SecurityTrace
from lirix.core.hook_manager import HookManager
from lirix.core.trace_recorder import TraceRecorder


def test_hook_trace_recorder_is_context_isolated_under_concurrency() -> None:
    mgr = HookManager(contract_mode="enforce")

    async def noop_hook(*args: object, **kwargs: object) -> None:
        await asyncio.sleep(0.01)

    mgr.register_hook(HOOK_PRE_VALIDATE, noop_hook)

    async def _run(tag: str, gate: asyncio.Event) -> SecurityTrace:
        trace = SecurityTrace.new(
            correlation_id=tag, intent="swap", payload={"to": "0x1", "data": "0x"}
        )
        mgr.bind_trace_recorder(TraceRecorder(trace=trace))
        await gate.wait()
        try:
            await mgr.ainvoke_hooks_isolated(
                HOOK_PRE_VALIDATE,
                intent="swap",
                payload={"to": "0x1", "data": "0x"},
            )
        finally:
            mgr.bind_trace_recorder(None)
        return trace

    async def _main() -> tuple[SecurityTrace, SecurityTrace]:
        gate = asyncio.Event()
        t1 = asyncio.create_task(_run("c1", gate))
        t2 = asyncio.create_task(_run("c2", gate))
        await asyncio.sleep(0)
        gate.set()
        return await asyncio.gather(t1, t2)

    a, b = asyncio.run(_main())
    assert len(a.steps) == 1
    assert len(b.steps) == 1
    assert a.steps[0].layer == "hooks"
    assert b.steps[0].layer == "hooks"


def test_hook_trace_recorder_is_context_isolated_under_sync_concurrency() -> None:
    mgr = HookManager(contract_mode="enforce")

    def noop_hook(*args: object, **kwargs: object) -> None:
        return None

    mgr.register_hook(HOOK_PRE_VALIDATE, noop_hook)

    def _run(tag: str) -> SecurityTrace:
        trace = SecurityTrace.new(
            correlation_id=tag, intent="swap", payload={"to": "0x1", "data": "0x"}
        )
        mgr.bind_trace_recorder(TraceRecorder(trace=trace))
        try:
            mgr.invoke_hooks_isolated(
                HOOK_PRE_VALIDATE,
                intent="swap",
                payload={"to": "0x1", "data": "0x"},
            )
        finally:
            mgr.bind_trace_recorder(None)
        return trace

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(_run, "c1").result()
        b = pool.submit(_run, "c2").result()

    assert len(a.steps) == 1
    assert len(b.steps) == 1
    assert a.steps[0].layer == "hooks"
    assert b.steps[0].layer == "hooks"
