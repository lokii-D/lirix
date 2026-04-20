# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from web3 import AsyncWeb3, Web3
from web3.providers import HTTPProvider
from web3.providers.rpc import AsyncHTTPProvider

from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L4
from lirix.core.exceptions import (
    CircuitBreakerOpenException,
    RPCQuotaExhaustedException,
    RPCUnavailableException,
)
from lirix.core.hook_manager import HookManager

# 多节点高度差超过该阈值视为污染（Fail-Closed，禁止用旧缓存冒充最新）
BLOCK_HEIGHT_SPREAD_THRESHOLD: int = 2
# 同一端点连续 RPC 传输层失败次数达到该值则断路器 OPEN
CIRCUIT_FAILURE_THRESHOLD: int = 3


class RPCManager:
    """L4：多 RPC 并发对账 + 断路器；无链上状态缓存，失败即阻断。"""

    def __init__(
        self,
        config: LirixConfig,
        *,
        request_timeout: int = 30,
        hooks: Optional[HookManager] = None,
    ) -> None:
        self._config = config
        self._hooks = hooks
        self._timeout = request_timeout
        self._lock = threading.Lock()
        self._failures: Dict[str, int] = {}
        self._open: Dict[str, bool] = {}
        self._sync_web3: Optional[Web3] = None
        self._async_web3: Optional[AsyncWeb3[Any]] = None
        self._last_url: Optional[str] = None

    def reset_circuit_breakers(self) -> None:
        """测试或运维复位：清空断路器状态（不缓存历史区块）。"""
        with self._lock:
            self._failures.clear()
            self._open.clear()
            self._sync_web3 = None
            self._async_web3 = None
            self._last_url = None

    def _eligible_urls(self) -> List[str]:
        return [u for u in self._config.rpc_urls if not self._open.get(u, False)]

    def _record_transport_failure(self, url: str) -> None:
        n = self._failures.get(url, 0) + 1
        self._failures[url] = n
        if n >= CIRCUIT_FAILURE_THRESHOLD:
            self._open[url] = True

    @staticmethod
    def _is_quota_exhausted(exc: BaseException) -> bool:
        text = str(exc)
        return "429" in text or "Too Many Requests" in text

    def _raise_quota_exhausted(self, url: str, exc: BaseException) -> None:
        raise RPCQuotaExhaustedException(
            human_readable_reason="RPC returned HTTP 429 / Too Many Requests during block fetch.",
            context={"layer": "L4", "url": url},
        ) from exc

    def _record_transport_success(self, url: str) -> None:
        self._failures[url] = 0
        self._open[url] = False

    def _prepare_reconcile_locked(self) -> List[str]:
        if not self._config.rpc_urls:
            raise RPCUnavailableException(
                human_readable_reason="rpc_urls is empty; cannot reconcile chain height.",
                context={"layer": "L4", "reason": "rpc_urls_empty"},
            )
        eligible = self._eligible_urls()
        if not eligible:
            raise CircuitBreakerOpenException(
                human_readable_reason=(
                    "All RPC endpoints have open circuit breakers; reconciliation blocked."
                ),
                context={"layer": "L4", "reason": "all_breakers_open"},
            )
        return list(eligible)

    def _fetch_block_number_sync(self, url: str) -> Tuple[str, int]:
        provider = HTTPProvider(url, request_kwargs={"timeout": self._timeout})
        w3 = Web3(provider)
        if not w3.is_connected():
            raise ConnectionError(f"not connected: {url}")
        try:
            bn = int(w3.eth.block_number)
        except BaseException as exc:
            if self._is_quota_exhausted(exc):
                self._raise_quota_exhausted(url, exc)
            raise
        return url, bn

    def sync_reconcile(self) -> int:
        """并发拉取各健康节点区块高度；高度离散过大则 Fail-Closed。"""
        with self._lock:
            eligible = self._prepare_reconcile_locked()

        heights: Dict[str, int] = {}
        errors: Dict[str, BaseException] = {}
        max_workers = max(1, len(eligible))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(self._fetch_block_number_sync, u): u for u in eligible}
            for fut in as_completed(futures):
                url = futures[fut]
                try:
                    u, bn = fut.result()
                    heights[u] = bn
                except BaseException as exc:  # noqa: BLE001 — 传输层
                    errors[url] = exc

        with self._lock:
            if errors and any(self._is_quota_exhausted(exc) for exc in errors.values()):
                first = next(exc for exc in errors.values() if self._is_quota_exhausted(exc))
                raise RPCQuotaExhaustedException(
                    human_readable_reason=(
                        "RPC returned HTTP 429 / Too Many Requests during block fetch."
                    ),
                    context={"layer": "L4", "failed": {k: str(v) for k, v in errors.items()}},
                ) from first

            for u in eligible:
                if u in heights:
                    self._record_transport_success(u)
                else:
                    self._record_transport_failure(u)

            if len(heights) != len(eligible):
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "One or more RPC endpoints failed during block height reconciliation."
                    ),
                    context={
                        "layer": "L4",
                        "failed": {k: str(v) for k, v in errors.items()},
                        "ok_count": len(heights),
                        "expected": len(eligible),
                    },
                )

            values = list(heights.values())
            spread = max(values) - min(values)
            if spread > BLOCK_HEIGHT_SPREAD_THRESHOLD:
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "RPC node block heights diverge beyond the allowed threshold; "
                        "treating cluster state as contaminated (fail-closed)."
                    ),
                    context={
                        "layer": "L4",
                        "heights": dict(heights),
                        "spread": spread,
                        "threshold": BLOCK_HEIGHT_SPREAD_THRESHOLD,
                    },
                )

            chosen = sorted(heights.keys())[0]
            self._last_url = chosen
            self._sync_web3 = Web3(HTTPProvider(chosen, request_kwargs={"timeout": self._timeout}))
            self._async_web3 = None
            bn = max(values)
            h = self._hooks
            if h is not None:
                h.invoke_hooks_isolated(
                    HOOK_LAYER_L4,
                    layer="L4",
                    block_number=bn,
                    mode="sync",
                    timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
                )
            return bn

    def sync_web3(self) -> Web3:
        """返回最近一次 sync_reconcile 成功绑定的 Web3（必须先 reconcile）。"""
        with self._lock:
            if self._sync_web3 is None:
                raise RPCUnavailableException(
                    human_readable_reason="No active Web3; call sync_reconcile() first.",
                    context={"layer": "L4", "reason": "web3_not_ready"},
                )
            return self._sync_web3

    async def async_reconcile(self) -> int:
        """异步并发对账；语义与 sync_reconcile 一致。"""
        with self._lock:
            eligible = self._prepare_reconcile_locked()

        tasks = [self._fetch_block_number_async(u) for u in eligible]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        heights: Dict[str, int] = {}
        errors: Dict[str, BaseException] = {}
        for url, res in zip(eligible, outcomes):
            if isinstance(res, BaseException):
                errors[url] = res
            else:
                u, bn = res
                heights[u] = bn

        with self._lock:
            if errors and any(self._is_quota_exhausted(exc) for exc in errors.values()):
                first = next(exc for exc in errors.values() if self._is_quota_exhausted(exc))
                raise RPCQuotaExhaustedException(
                    human_readable_reason=(
                        "RPC returned HTTP 429 / Too Many Requests during block fetch."
                    ),
                    context={"layer": "L4", "failed": {k: str(v) for k, v in errors.items()}},
                ) from first

            for u in eligible:
                if u in heights:
                    self._record_transport_success(u)
                else:
                    self._record_transport_failure(u)

            if len(heights) != len(eligible):
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "One or more RPC endpoints failed during block height reconciliation."
                    ),
                    context={
                        "layer": "L4",
                        "failed": {k: str(v) for k, v in errors.items()},
                        "ok_count": len(heights),
                        "expected": len(eligible),
                    },
                )

            values = list(heights.values())
            spread = max(values) - min(values)
            if spread > BLOCK_HEIGHT_SPREAD_THRESHOLD:
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "RPC node block heights diverge beyond the allowed threshold; "
                        "treating cluster state as contaminated (fail-closed)."
                    ),
                    context={
                        "layer": "L4",
                        "heights": dict(heights),
                        "spread": spread,
                        "threshold": BLOCK_HEIGHT_SPREAD_THRESHOLD,
                    },
                )

            chosen = sorted(heights.keys())[0]
            self._last_url = chosen
            self._async_web3 = AsyncWeb3(
                AsyncHTTPProvider(chosen, request_kwargs={"timeout": self._timeout})
            )
            self._sync_web3 = None
            bn = max(values)
            h = self._hooks
            if h is not None:
                h.invoke_hooks_isolated(
                    HOOK_LAYER_L4,
                    layer="L4",
                    block_number=bn,
                    mode="async",
                    timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
                )
            return bn

    async def _fetch_block_number_async(self, url: str) -> Tuple[str, int]:
        provider = AsyncHTTPProvider(url, request_kwargs={"timeout": self._timeout})
        w3 = AsyncWeb3(provider)
        if not await w3.is_connected():
            raise ConnectionError(f"not connected: {url}")
        try:
            bn = int(await w3.eth.block_number)
        except BaseException as exc:
            if self._is_quota_exhausted(exc):
                self._raise_quota_exhausted(url, exc)
            raise
        return url, bn

    def async_web3(self) -> AsyncWeb3[Any]:
        """返回最近一次 async_reconcile 成功绑定的 AsyncWeb3。"""
        with self._lock:
            if self._async_web3 is None:
                raise RPCUnavailableException(
                    human_readable_reason="No active AsyncWeb3; call async_reconcile() first.",
                    context={"layer": "L4", "reason": "async_web3_not_ready"},
                )
            return self._async_web3
