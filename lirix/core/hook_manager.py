# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
import threading
from collections import defaultdict
from queue import Empty, Queue
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from lirix.audit.logger import AuditLogger
from lirix.core.canonical_taxonomy import retry_allowed_for_hook_error_code
from lirix.core.constants import (
    DEFAULT_HOOK_FAILURE_LEVEL,
    HOOK_CONTRACT_SCHEMA_VERSION,
    HOOK_ERR_ASYNC_REQUIRED,
    HOOK_ERR_CONTRACT_VIOLATION,
    HOOK_ERR_DECISION_REJECTED,
    HOOK_ERR_PATCH_FORBIDDEN,
    HOOK_ERR_PATCH_TARGET_FORBIDDEN,
    HOOK_ERR_RUNTIME,
    HOOK_ERR_TIMEOUT,
    HOOK_FAILURE_LEVELS,
    HOOK_PATCH_ALLOWED_POINTS,
    HOOK_PAYLOAD_REQUIRED_FIELDS,
    HOOK_POINT_CAPABILITIES,
    HOOK_WARN_CONTRACT,
    HOOK_WARN_CONTRACT_SHADOW,
    HOOK_WARN_PATCH_FORBIDDEN,
    HOOK_WARN_PATCH_FORBIDDEN_SHADOW,
    HOOK_WARN_PATCH_TARGET,
    HOOK_WARN_PATCH_TARGET_SHADOW,
    PREDEFINED_HOOK_POINTS,
    canonicalize_error_code,
)
from lirix.core.evidence import ExecutionEvidence
from lirix.core.evidence_semantics import normalize_non_empty_token
from lirix.core.exceptions import (
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    LirixSecurityException,
)
from lirix.core.hook_contract import (
    HookContractRegistry,
    HookDecision,
    HookPatch,
    ReadonlyHookPayload,
    apply_hook_patch,
)
from lirix.core.status_aggregation import aggregate_statuses
from lirix.core.trace_recorder import TraceRecorder

# Wall-clock ceiling for ``ainvoke_hooks`` (non-isolated async hook path).
_AINVOKE_HOOKS_WALL_TIMEOUT_SEC = 30.0

HookCallback = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


def _assert_hook_accepts_lirix_invoke(callback: HookCallback) -> None:
    """Lirix Hook 约定：必须同时接受 *args 与 **kwargs，便于核心无耦合传参。"""
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError) as exc:
        raise LirixSecurityException(
            human_readable_reason="Unable to inspect hook callback signature",
            context={"layer": "hooks", "reason": "hook_signature_inspection_failed"},
        ) from exc
    kinds = {p.kind for p in sig.parameters.values()}
    if inspect.Parameter.VAR_KEYWORD not in kinds:
        raise LirixSecurityException(
            human_readable_reason=(
                "Lirix hook callbacks must accept **kwargs (e.g. def hook(*args, **kwargs): ...)."
            ),
            context={"layer": "hooks", "reason": "hook_signature_missing_kwargs"},
        )
    if inspect.Parameter.VAR_POSITIONAL not in kinds:
        raise LirixSecurityException(
            human_readable_reason=(
                "Lirix hook callbacks must accept *args (e.g. def hook(*args, **kwargs): ...)."
            ),
            context={"layer": "hooks", "reason": "hook_signature_missing_args"},
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
        except (
            BaseException
        ) as exc:  # noqa: BLE001 — isolate arbitrary hook failures from the worker thread
            q.put(("err", exc))

    th = threading.Thread(target=_worker, daemon=True, name="lirix-hook-isolated")
    th.start()
    th.join(timeout_sec)
    if th.is_alive():
        return ("timeout", None)
    try:
        return q.get_nowait()
    except Empty:  # pragma: no cover — 竞态下线程未及时入队
        return (
            "err",
            LirixSecurityException(
                human_readable_reason="Hook thread exited without a result.",
                context={"layer": "hooks", "reason": "hook_thread_empty_queue"},
            ),
        )


class HookManager:
    """插件 Hook 调度器：仅负责注册与调用，不包含任何业务实现。"""

    def __init__(self, *, contract_mode: str = "legacy") -> None:
        self._registry: DefaultDict[str, List[HookCallback]] = defaultdict(list)
        self._lock = threading.Lock()
        self._audit_for_timeouts: Optional[AuditLogger] = None
        self._contract_mode = contract_mode
        self._trace_recorder: Optional[TraceRecorder] = None
        self._trace_recorder_ctx: contextvars.ContextVar[Optional[TraceRecorder]] = (
            contextvars.ContextVar("lirix_hook_trace_recorder", default=None)
        )
        self._contract_registry = HookContractRegistry()
        for point, required in HOOK_PAYLOAD_REQUIRED_FIELDS.items():
            self._contract_registry.register(point, required)

    def bind_audit_logger(self, audit: Optional[AuditLogger]) -> None:
        """绑定审计器：钩子墙钟超时时写入系统审计行（不触发 on_audit_log）。"""
        self._audit_for_timeouts = audit

    def bind_trace_recorder(self, recorder: Optional[TraceRecorder]) -> None:
        """Bind a trace recorder to enforce hook->trace truth-source recording."""
        self._trace_recorder = recorder
        self._trace_recorder_ctx.set(recorder)

    def has_bound_trace_recorder(self) -> bool:
        return self._trace_recorder_ctx.get() is not None or self._trace_recorder is not None

    def _active_trace_recorder(self) -> Optional[TraceRecorder]:
        rec = self._trace_recorder_ctx.get()
        if rec is not None:
            return rec
        return self._trace_recorder

    @staticmethod
    def _aggregate_isolated_hook_trace_status(results: Sequence[Dict[str, Any]]) -> str:
        """Collapse isolated hook invocation results into a single trace status token."""
        return aggregate_statuses(
            "ok" if bool(item.get("ok", True)) else "degraded" for item in results
        )

    def _maybe_record_hook_trace(
        self,
        *,
        hook_point: str,
        results: List[Dict[str, Any]],
        payload_contract: Dict[str, Any],
        mode: str,
    ) -> None:
        requires = bool(HOOK_POINT_CAPABILITIES.get(hook_point, {}).get("requires_trace", False))
        if not requires:
            return
        rec = self._active_trace_recorder()
        if rec is None:
            # Compatible default: HookManager can be used standalone in unit tests
            # and embedding contexts. Lirix binds a per-invocation recorder to
            # guarantee hook-to-trace truth-source recording in production flows.
            return
        trace_status = self._aggregate_isolated_hook_trace_status(results)
        rec.record_step(
            ExecutionEvidence(
                layer="hooks",
                stage=normalize_non_empty_token(hook_point, field="hook_point"),
                status=trace_status,
                details={
                    "mode": mode,
                    "payload_contract": dict(payload_contract),
                    "results": list(results),
                },
            )
        )

    def register_hook(self, hook_point: str, callback: HookCallback) -> None:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        _assert_hook_accepts_lirix_invoke(callback)
        with self._lock:
            self._registry[hook_point].append(callback)

    def clear(self, hook_point: Optional[str] = None) -> None:
        with self._lock:
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

    @staticmethod
    def _payload_contract_state(hook_point: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        required = HOOK_PAYLOAD_REQUIRED_FIELDS.get(hook_point, frozenset())
        missing = sorted(k for k in required if k not in kwargs)
        return {
            "version": HOOK_CONTRACT_SCHEMA_VERSION,
            "required_fields": sorted(required),
            "missing_fields": missing,
            "valid": len(missing) == 0,
        }

    def _failure_level_of(self, result: Any) -> str:
        if isinstance(result, HookDecision) and result.failure_level in HOOK_FAILURE_LEVELS:
            return result.failure_level
        return DEFAULT_HOOK_FAILURE_LEVEL

    def _wrap_payload_for_contract(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        wrapped = dict(kwargs)
        payload = wrapped.get("payload")
        if isinstance(payload, dict):
            wrapped["payload"] = ReadonlyHookPayload.from_mapping(payload)
        return wrapped

    def _result_contract_state(self, result: Any) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "mode": self._contract_mode,
            "valid": self._contract_registry.validate_result(result),
            "result_type": type(result).__name__,
            "allowed_types": ["NoneType", "HookDecision", "HookPatch", "HookAnnotation"],
        }
        if isinstance(result, HookPatch):
            base["patch_target"] = result.target
            base["patch_target_valid"] = result.target == "payload"
        return base

    def _hook_ok_result(
        self, hook_point: str, result: Any, payload_contract: Dict[str, Any]
    ) -> Dict[str, Any]:
        result_contract = self._result_contract_state(result)
        contract_ok = payload_contract.get("valid", True) and result_contract["valid"]
        patch_allowed = True
        if isinstance(result, HookPatch):
            patch_allowed = bool(
                HOOK_POINT_CAPABILITIES.get(hook_point, {}).get(
                    "allows_patch", hook_point in HOOK_PATCH_ALLOWED_POINTS
                )
            )
            if self._contract_mode == "shadow":
                patch_allowed = False
            # Patch target governance (only payload is allowed).
            if result.target != "payload":
                if self._contract_mode == "enforce":
                    return self._hook_error_result(
                        hook_point,
                        error="hook_patch_target_not_allowed",
                        error_code=HOOK_ERR_PATCH_TARGET_FORBIDDEN,
                        error_type="contract_violation",
                        payload_contract=payload_contract,
                        result_contract=result_contract,
                        failure_level="fatal",
                    )
                warning_code = (
                    HOOK_WARN_PATCH_TARGET_SHADOW
                    if self._contract_mode == "shadow"
                    else HOOK_WARN_PATCH_TARGET
                )
                return {
                    "ok": True,
                    "hook_point": hook_point,
                    "schema_version": HOOK_CONTRACT_SCHEMA_VERSION,
                    "error_code": warning_code,
                    "canonical_error_code": canonicalize_error_code(warning_code),
                    "error_type": "contract_warning",
                    "retryable": False,
                    "payload_contract": payload_contract,
                    "result_contract": result_contract,
                    "failure_level": (
                        "shadow_only" if self._contract_mode == "shadow" else "observe_only"
                    ),
                    "contract_warning": True,
                    "shadow_only": self._contract_mode == "shadow",
                    "patch_allowed": False,
                    "result": result,
                }

            if self._contract_mode == "enforce" and not patch_allowed:
                return self._hook_error_result(
                    hook_point,
                    error="hook_patch_not_allowed_at_point",
                    error_code=HOOK_ERR_PATCH_FORBIDDEN,
                    error_type="contract_violation",
                    payload_contract=payload_contract,
                    result_contract=result_contract,
                    failure_level="fatal",
                )
            if self._contract_mode in {"warn", "shadow"} and not patch_allowed:
                warning_code = (
                    HOOK_WARN_PATCH_FORBIDDEN_SHADOW
                    if self._contract_mode == "shadow"
                    else HOOK_WARN_PATCH_FORBIDDEN
                )
                return {
                    "ok": True,
                    "hook_point": hook_point,
                    "schema_version": HOOK_CONTRACT_SCHEMA_VERSION,
                    "error_code": warning_code,
                    "canonical_error_code": canonicalize_error_code(warning_code),
                    "error_type": "contract_warning",
                    "retryable": False,
                    "payload_contract": payload_contract,
                    "result_contract": result_contract,
                    "failure_level": (
                        "shadow_only" if self._contract_mode == "shadow" else "observe_only"
                    ),
                    "contract_warning": True,
                    "shadow_only": self._contract_mode == "shadow",
                    "patch_allowed": False,
                    "result": result,
                }
        if (
            isinstance(result, HookDecision)
            and result.status.lower() in {"reject", "rejected", "blocked"}
            and result.failure_level == "fatal"
            and self._contract_mode == "enforce"
        ):
            return self._hook_error_result(
                hook_point,
                error=f"hook_decision_rejected:{result.reason}",
                error_code=HOOK_ERR_DECISION_REJECTED,
                error_type="policy_rejection",
                payload_contract=payload_contract,
                result_contract=result_contract,
                failure_level="fatal",
            )
        if self._contract_mode == "enforce" and not contract_ok:
            return self._hook_error_result(
                hook_point,
                error="hook_contract_violation",
                error_code=HOOK_ERR_CONTRACT_VIOLATION,
                error_type="contract_violation",
                payload_contract=payload_contract,
                result_contract=result_contract,
                failure_level="fatal",
            )
        if self._contract_mode in {"warn", "shadow"} and not contract_ok:
            warning_code = (
                HOOK_WARN_CONTRACT_SHADOW if self._contract_mode == "shadow" else HOOK_WARN_CONTRACT
            )
            return {
                "ok": True,
                "hook_point": hook_point,
                "schema_version": HOOK_CONTRACT_SCHEMA_VERSION,
                "error_code": warning_code,
                "canonical_error_code": canonicalize_error_code(warning_code),
                "error_type": "contract_warning",
                "retryable": False,
                "payload_contract": payload_contract,
                "result_contract": result_contract,
                "failure_level": "observe_only" if self._contract_mode == "warn" else "shadow_only",
                "contract_warning": True,
                "shadow_only": self._contract_mode == "shadow",
                "result": result,
            }
        return {
            "ok": True,
            "hook_point": hook_point,
            "schema_version": HOOK_CONTRACT_SCHEMA_VERSION,
            "error_code": None,
            "canonical_error_code": None,
            "error_type": None,
            "retryable": False,
            "payload_contract": payload_contract,
            "result_contract": result_contract,
            "failure_level": self._failure_level_of(result),
            "patch_allowed": patch_allowed,
            "shadow_only": self._contract_mode == "shadow",
            "result": result,
        }

    @staticmethod
    def _hook_error_result(
        hook_point: str,
        *,
        error: str,
        error_code: str,
        error_type: str,
        payload_contract: Dict[str, Any],
        result_contract: Optional[Dict[str, Any]] = None,
        failure_level: str = DEFAULT_HOOK_FAILURE_LEVEL,
    ) -> Dict[str, Any]:
        return {
            "ok": False,
            "hook_point": hook_point,
            "schema_version": HOOK_CONTRACT_SCHEMA_VERSION,
            "error": error,
            "error_code": error_code,
            "canonical_error_code": canonicalize_error_code(error_code),
            "error_type": error_type,
            "retryable": retry_allowed_for_hook_error_code(error_code),
            "payload_contract": payload_contract,
            "result_contract": result_contract or {},
            "failure_level": failure_level,
        }

    def invoke_hooks(self, hook_point: str, *args: Any, **kwargs: Any) -> List[Any]:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        with self._lock:
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
        with self._lock:
            callbacks = list(self._registry.get(hook_point, ()))
        results: List[Dict[str, Any]] = []
        mutable_payload = kwargs.get("payload") if isinstance(kwargs.get("payload"), dict) else None
        in_kwargs = (
            self._wrap_payload_for_contract(kwargs)
            if self._contract_mode in {"warn", "shadow", "enforce"}
            else kwargs
        )
        payload_contract = self._payload_contract_state(hook_point, in_kwargs)
        for cb in callbacks:
            if inspect.iscoroutinefunction(cb):
                results.append(
                    self._hook_error_result(
                        hook_point,
                        error="async_hook_requires_ainvoke",
                        error_code=HOOK_ERR_ASYNC_REQUIRED,
                        error_type="contract_violation",
                        payload_contract=payload_contract,
                    )
                )
                continue
            if timeout_sec is not None and timeout_sec > 0:
                kind, payload = _invoke_sync_hook_threaded(cb, args, in_kwargs, float(timeout_sec))
                if kind == "timeout":
                    self._emit_hook_timeout_audit(hook_point, float(timeout_sec))
                    results.append(
                        self._hook_error_result(
                            hook_point,
                            error=f"timeout_after_{timeout_sec}s",
                            error_code=HOOK_ERR_TIMEOUT,
                            error_type="timeout",
                            payload_contract=payload_contract,
                        )
                    )
                    continue
                if kind == "lirix":
                    raise payload  # LirixSecurityException
                if kind == "err":
                    results.append(
                        self._hook_error_result(
                            hook_point,
                            error=f"{type(payload).__name__}: {payload}",
                            error_code=HOOK_ERR_RUNTIME,
                            error_type=type(payload).__name__,
                            payload_contract=payload_contract,
                        )
                    )
                    continue
                res = self._hook_ok_result(hook_point, payload, payload_contract)
                results.append(res)
                if (
                    isinstance(payload, HookPatch)
                    and mutable_payload is not None
                    and res.get("ok")
                    and res.get("patch_allowed", True)
                ):
                    # Record explicit patch-key boundary for deterministic audit/evidence review.
                    res["patch_applied_fields"] = sorted(str(k) for k in payload.updates)
                    apply_hook_patch(mutable_payload, payload)
                continue
            try:
                out = cb(*args, **in_kwargs)
                res = self._hook_ok_result(hook_point, out, payload_contract)
                results.append(res)
                if (
                    isinstance(out, HookPatch)
                    and mutable_payload is not None
                    and res.get("ok")
                    and res.get("patch_allowed", True)
                ):
                    # Record explicit patch-key boundary for deterministic audit/evidence review.
                    res["patch_applied_fields"] = sorted(str(k) for k in out.updates)
                    apply_hook_patch(mutable_payload, out)
            except LirixSecurityException:
                raise
            except (
                Exception
            ) as exc:  # noqa: BLE001 — hook isolation: record third-party callback failures
                results.append(
                    self._hook_error_result(
                        hook_point,
                        error=f"{type(exc).__name__}: {exc}",
                        error_code=HOOK_ERR_RUNTIME,
                        error_type=type(exc).__name__,
                        payload_contract=payload_contract,
                    )
                )
        self._maybe_record_hook_trace(
            hook_point=hook_point,
            results=results,
            payload_contract=payload_contract,
            mode=self._contract_mode,
        )
        return results

    async def ainvoke_hooks(self, hook_point: str, *args: Any, **kwargs: Any) -> List[Any]:
        if hook_point not in PREDEFINED_HOOK_POINTS:
            raise HookUnknownPointException(hook_point=hook_point)
        with self._lock:
            callbacks = list(self._registry.get(hook_point, ()))
        results: List[Any] = []
        loop = asyncio.get_running_loop()
        wall_timeout = float(_AINVOKE_HOOKS_WALL_TIMEOUT_SEC)
        for cb in callbacks:
            try:
                if inspect.iscoroutinefunction(cb):
                    results.append(
                        await asyncio.wait_for(cb(*args, **kwargs), timeout=wall_timeout)
                    )
                else:
                    exec_fn: Callable[..., Any] = functools.partial(
                        cast(Callable[..., Any], cb), *args, **kwargs
                    )
                    results.append(
                        await asyncio.wait_for(
                            loop.run_in_executor(None, exec_fn), timeout=wall_timeout
                        )
                    )
            except asyncio.TimeoutError as exc:
                raise HookExecutionException(
                    human_readable_reason="Hook exceeded wall-clock timeout during ainvoke_hooks.",
                    context={
                        "hook_point": hook_point,
                        "timeout_sec": wall_timeout,
                    },
                ) from exc
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
        with self._lock:
            callbacks = list(self._registry.get(hook_point, ()))

        # Fast path: if all hooks are sync, delegate to the sync implementation.
        # This keeps behavior consistent across sync/async entrypoints and makes it
        # easy to monkeypatch `invoke_hooks_isolated` in tests.
        if not callbacks or all(not inspect.iscoroutinefunction(cb) for cb in callbacks):
            loop = asyncio.get_running_loop()
            fast_fn = functools.partial(
                self.invoke_hooks_isolated,
                hook_point,
                *args,
                timeout_sec=timeout_sec,
                **kwargs,
            )
            return await loop.run_in_executor(None, fast_fn)

        results: List[Dict[str, Any]] = []
        mutable_payload = kwargs.get("payload") if isinstance(kwargs.get("payload"), dict) else None
        in_kwargs = (
            self._wrap_payload_for_contract(kwargs)
            if self._contract_mode in {"warn", "shadow", "enforce"}
            else kwargs
        )
        payload_contract = self._payload_contract_state(hook_point, in_kwargs)
        loop = asyncio.get_running_loop()
        for cb in callbacks:
            try:
                if timeout_sec is not None and timeout_sec > 0:
                    to = float(timeout_sec)
                    if inspect.iscoroutinefunction(cb):
                        out = await asyncio.wait_for(cb(*args, **in_kwargs), timeout=to)
                    else:
                        exec_fn: Callable[[], Any] = functools.partial(
                            cast(Callable[..., Any], cb), *args, **in_kwargs
                        )
                        out = await asyncio.wait_for(
                            loop.run_in_executor(None, exec_fn), timeout=to
                        )
                else:
                    if inspect.iscoroutinefunction(cb):
                        out = await cb(*args, **in_kwargs)
                    else:
                        out = cb(*args, **in_kwargs)
                res = self._hook_ok_result(hook_point, out, payload_contract)
                results.append(res)
                if (
                    isinstance(out, HookPatch)
                    and mutable_payload is not None
                    and res.get("ok")
                    and res.get("patch_allowed", True)
                ):
                    # Record explicit patch-key boundary for deterministic audit/evidence review.
                    res["patch_applied_fields"] = sorted(str(k) for k in out.updates)
                    apply_hook_patch(mutable_payload, out)
            except asyncio.TimeoutError:
                self._emit_hook_timeout_audit(hook_point, float(timeout_sec or 0))
                results.append(
                    self._hook_error_result(
                        hook_point,
                        error=f"timeout_after_{timeout_sec}s",
                        error_code=HOOK_ERR_TIMEOUT,
                        error_type="timeout",
                        payload_contract=payload_contract,
                    )
                )
            except LirixSecurityException:
                raise
            except (
                Exception
            ) as exc:  # noqa: BLE001 — hook isolation: record third-party callback failures
                results.append(
                    self._hook_error_result(
                        hook_point,
                        error=f"{type(exc).__name__}: {exc}",
                        error_code=HOOK_ERR_RUNTIME,
                        error_type=type(exc).__name__,
                        payload_contract=payload_contract,
                    )
                )
        self._maybe_record_hook_trace(
            hook_point=hook_point,
            results=results,
            payload_contract=payload_contract,
            mode=self._contract_mode,
        )
        return results
