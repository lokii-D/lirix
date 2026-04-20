# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import functools
import inspect
import threading
from collections import defaultdict
from queue import Empty, Queue
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from lirix.core.constants import PREDEFINED_HOOK_POINTS
from lirix.core.exceptions import (
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    LirixSecurityException,
)

if TYPE_CHECKING:
    from lirix.audit.logger import AuditLogger

HookCallback = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


def _assert_hook_accepts_lirix_invoke(callback: HookCallback) -> None:
    """Lirix Hook 约定：必须同时接受 *args 与 **kwargs，便于核心无耦合传参。"""
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Unable to inspect hook callback signature") from exc
    kinds = {p.kind for p in sig.parameters.values()}
    if inspect.Parameter.VAR_KEYWORD not in kinds:
        raise RuntimeError(
            "Lirix hook callbacks must accept **kwargs (e.g. def hook(*args, **kwargs): ...)."
        )
    if inspect.Parameter.VAR_POSITIONAL not in kinds:
        raise RuntimeError(
            "Lirix hook callbacks must accept *args (e.g. def hook(*args, **kwargs): ...)."
        )


def _invoke_sync_hook_threaded(
    cb: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    timeout_sec: float,
) -> Tuple[str, Any]:
    """在独立线程中执行同步钩子；返回 (kind, payload)。

    kind 为 ``ok`` | ``timeout`` | ``err`` | ``lirix``（LirixSecurityException 实例）。
    """
    q: Queue[Tuple[str, Any]] = Queue(maxsize=1)

    def _worker() -> None:
        try:
            q.put(("ok", cb(*args, **kwargs)))
        except LirixSecurityException as exc:
            q.put(("lirix", exc))
        except BaseException as exc:  # noqa: BLE001
            q.put(("err", exc))

    th = threading.Thread(target=_worker, daemon=True, name="lirix-hook-isolated")
    th.start()
    th.join(timeout_sec)
    if th.is_alive():
        return ("timeout", None)
    try:
        return q.get_nowait()
    except Empty:  # pragma: no cover — 竞态下线程未及时入队
        return ("err", RuntimeError("Hook thread exited without a result."))


class HookManager:
    """插件 Hook 调度器：仅负责注册与调用，不包含任何业务实现。"""

    def __init__(self) -> None:
        self._registry: DefaultDict[str, List[HookCallback]] = defaultdict(list)
        self._audit_for_timeouts: Optional[AuditLogger] = None

    def bind_audit_logger(self, audit: Optional[AuditLogger]) -> None:
        """绑定审计器：钩子墙钟超时时写入系统审计行（不触发 on_audit_log）。"""
        self._audit_for_timeouts = audit

    def register_hook(self, hook_point: str, callback: HookCallback) -> None:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        _assert_hook_accepts_lirix_invoke(callback)
        self._registry[hook_point].append(callback)

    def clear(self, hook_point: Optional[str] = None) -> None:
        if hook_point is None:
            self._registry.clear()
            return
        if hook_point in self._registry:
            del self._registry[hook_point]

    def _emit_hook_timeout_audit(self, hook_point: str, timeout_sec: float) -> None:
        audit = self._audit_for_timeouts
        if audit is None:
            return
        audit.emit_system_event(
            blocked_by_layer="hooks",
            risk_level="high",
            reason=(
                f"Isolated hook exceeded wall-clock timeout ({timeout_sec}s); "
                f"skipped hook_point={hook_point}."
            ),
            context={"hook_point": hook_point, "timeout_sec": timeout_sec},
        )

    def invoke_hooks(self, hook_point: str, *args: Any, **kwargs: Any) -> List[Any]:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        callbacks = list(self._registry.get(hook_point, ()))
        results: List[Any] = []
        for cb in callbacks:
            if inspect.iscoroutinefunction(cb):
                raise HookAsyncContextException(hook_point=hook_point)
            try:
                results.append(cb(*args, **kwargs))
            except LirixSecurityException:
                raise
            except Exception as exc:
                raise HookExecutionException(
                    human_readable_reason="Hook raised an unexpected error.",
                    context={"hook_point": hook_point},
                ) from exc
        return results

    def invoke_hooks_isolated(
        self,
        hook_point: str,
        *args: Any,
        timeout_sec: Optional[float] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """顺序执行全部钩子；单钩异常与后续隔离（不抛 HookExecutionException）。

        LirixSecurityException 仍上抛。``timeout_sec`` 为墙钟秒数：超时则写系统审计并跳过该钩。
        """
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        callbacks = list(self._registry.get(hook_point, ()))
        results: List[Dict[str, Any]] = []
        for cb in callbacks:
            if inspect.iscoroutinefunction(cb):
                results.append(
                    {
                        "ok": False,
                        "hook_point": hook_point,
                        "error": "async_hook_requires_ainvoke",
                    }
                )
                continue
            if timeout_sec is not None and timeout_sec > 0:
                kind, payload = _invoke_sync_hook_threaded(cb, args, kwargs, float(timeout_sec))
                if kind == "timeout":
                    self._emit_hook_timeout_audit(hook_point, float(timeout_sec))
                    results.append(
                        {
                            "ok": False,
                            "hook_point": hook_point,
                            "error": f"timeout_after_{timeout_sec}s",
                        }
                    )
                    continue
                if kind == "lirix":
                    raise payload  # LirixSecurityException
                if kind == "err":
                    results.append(
                        {
                            "ok": False,
                            "hook_point": hook_point,
                            "error": f"{type(payload).__name__}: {payload}",
                        }
                    )
                    continue
                results.append({"ok": True, "hook_point": hook_point, "result": payload})
                continue
            try:
                out = cb(*args, **kwargs)
                results.append({"ok": True, "hook_point": hook_point, "result": out})
            except LirixSecurityException:
                raise
            except Exception as exc:  # noqa: BLE001 — 扩展钩子容错
                results.append(
                    {
                        "ok": False,
                        "hook_point": hook_point,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        return results

    async def ainvoke_hooks(self, hook_point: str, *args: Any, **kwargs: Any) -> List[Any]:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        callbacks = list(self._registry.get(hook_point, ()))
        results: List[Any] = []
        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    results.append(await cb(*args, **kwargs))
                else:
                    results.append(cb(*args, **kwargs))
            except LirixSecurityException:
                raise
            except Exception as exc:
                raise HookExecutionException(
                    human_readable_reason="Hook raised an unexpected error.",
                    context={"hook_point": hook_point},
                ) from exc
        return results

    async def ainvoke_hooks_isolated(
        self,
        hook_point: str,
        *args: Any,
        timeout_sec: Optional[float] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """异步路径下的钩子异常隔离（语义同 invoke_hooks_isolated）。"""
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        callbacks = list(self._registry.get(hook_point, ()))
        results: List[Dict[str, Any]] = []
        loop = asyncio.get_running_loop()
        for cb in callbacks:
            try:
                if timeout_sec is not None and timeout_sec > 0:
                    to = float(timeout_sec)
                    if inspect.iscoroutinefunction(cb):
                        out = await asyncio.wait_for(cb(*args, **kwargs), timeout=to)
                    else:
                        fn = functools.partial(cb, *args, **kwargs)
                        out = await asyncio.wait_for(loop.run_in_executor(None, fn), timeout=to)
                else:
                    if inspect.iscoroutinefunction(cb):
                        out = await cb(*args, **kwargs)
                    else:
                        out = cb(*args, **kwargs)
                results.append({"ok": True, "hook_point": hook_point, "result": out})
            except asyncio.TimeoutError:
                self._emit_hook_timeout_audit(hook_point, float(timeout_sec or 0))
                results.append(
                    {
                        "ok": False,
                        "hook_point": hook_point,
                        "error": f"timeout_after_{timeout_sec}s",
                    }
                )
            except LirixSecurityException:
                raise
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "ok": False,
                        "hook_point": hook_point,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        return results
