# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, cast

from web3 import AsyncWeb3, Web3
from web3.providers import HTTPProvider
from web3.providers.rpc import AsyncHTTPProvider

from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L4
from lirix.core.exceptions import (
    CircuitBreakerOpenException,
    LirixRPCError,
    RPCQuotaExhaustedException,
    RPCUnavailableException,
)
from lirix.core.hook_manager import HookManager


class LirixRPCTimeoutException(LirixRPCError):
    """Raised when quorum retries exceed a hard wall-clock budget."""

    pass


class LirixConsensusFailureException(LirixRPCError):
    """Raised when quorum hashing fails to reach a 2/3 consensus."""

    pass


# 多节点高度差超过该阈值视为污染（Fail-Closed，禁止用旧缓存冒充最新）
BLOCK_HEIGHT_SPREAD_THRESHOLD: int = 2
# 同一端点连续 RPC 传输层失败次数达到该值则断路器 OPEN
CIRCUIT_FAILURE_THRESHOLD: int = 3


class RPCManager:
    """L4：多 RPC 并发对账 + 断路器；无链上状态缓存，失败即阻断。"""

    CIRCUIT_COOLDOWN_SECONDS: int = 60
    HEALTH_SPREAD_THRESHOLD: int = BLOCK_HEIGHT_SPREAD_THRESHOLD

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
        self._cooldown_until: Dict[str, float] = {}
        self._sync_web3: Optional[Web3] = None
        self._async_web3: Optional[AsyncWeb3[Any]] = None
        self._last_url: Optional[str] = None
        self._last_selected_latency: Optional[float] = None
        self._last_error: Optional[Dict[str, Any]] = None

    def reset_circuit_breakers(self) -> None:
        """测试或运维复位：清空断路器状态（不缓存历史区块）。"""
        with self._lock:
            self._failures.clear()
            self._open.clear()
            self._cooldown_until.clear()
            self._sync_web3 = None
            self._async_web3 = None
            self._last_url = None
            self._last_selected_latency = None
            self._last_error = None

    def _eligible_urls(self) -> List[str]:
        return [u for u in self._config.rpc_urls if not self._open.get(u, False)]

    def _record_transport_failure(self, url: str) -> None:
        n = self._failures.get(url, 0) + 1
        self._failures[url] = n
        if n >= CIRCUIT_FAILURE_THRESHOLD:
            self._open[url] = True
            self._cooldown_until[url] = time.time() + self.CIRCUIT_COOLDOWN_SECONDS

    def _record_outcome(
        self,
        eligible: List[str],
        heights: Dict[str, int],
        errors: Dict[str, BaseException],
    ) -> None:
        for u in eligible:
            if u in heights:
                self._record_transport_success(u)
            else:
                self._record_transport_failure(u)

    def _classify_errors(self, errors: Dict[str, BaseException]) -> Dict[str, List[str]]:
        classified: Dict[str, List[str]] = {
            "quota_exhausted": [],
            "timeout": [],
            "transport": [],
            "other": [],
        }
        for url, exc in errors.items():
            if self._is_quota_exhausted(exc):
                classified["quota_exhausted"].append(url)
            elif isinstance(exc, TimeoutError):
                classified["timeout"].append(url)
            elif isinstance(exc, ConnectionError):
                classified["transport"].append(url)
            else:
                classified["other"].append(url)
        return classified

    def _health_context(self) -> Dict[str, Any]:
        return {
            "rpc_urls": list(self._config.rpc_urls),
            "last_url": self._last_url,
            "open_endpoints": [url for url, open_ in self._open.items() if open_],
            "failures": dict(self._failures),
            "cooldown_until": dict(self._cooldown_until),
            "request_timeout": self._timeout,
            "eligible_count": len(self._eligible_urls()),
        }

    def _failure_context(
        self,
        *,
        reason: str,
        errors: Optional[Dict[str, BaseException]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "layer": "L4",
            "reason": reason,
            "health": self._health_context(),
        }
        if errors:
            context["failed"] = {k: str(v) for k, v in errors.items()}
            context["classified"] = self._classify_errors(errors)
        if extra:
            context.update(extra)
        return context

    def _snapshot_health_locked(self) -> Dict[str, Any]:
        snapshot = self._health_context()
        snapshot["last_selected_latency"] = self._last_selected_latency
        return snapshot

    @staticmethod
    def _is_quota_exhausted(exc: BaseException) -> bool:
        text = str(exc)
        return "429" in text or "Too Many Requests" in text

    def _raise_quota_exhausted(self, url: str, exc: BaseException) -> None:
        raise RPCQuotaExhaustedException(
            human_readable_reason="RPC returned HTTP 429 / Too Many Requests during block fetch.",
            context=self._failure_context(reason="quota_exhausted", extra={"url": url}),
        ) from exc

    def _record_transport_success(self, url: str) -> None:
        if time.time() < self._cooldown_until.get(url, 0):
            return
        self._failures[url] = 0
        self._open[url] = False

    def _prepare_reconcile_locked(self) -> List[str]:
        if not self._config.rpc_urls:
            raise RPCUnavailableException(
                human_readable_reason="rpc_urls is empty; cannot reconcile chain height.",
                context=self._failure_context(reason="rpc_urls_empty"),
            )
        eligible = self._eligible_urls()
        if not eligible:
            raise CircuitBreakerOpenException(
                human_readable_reason=(
                    "All RPC endpoints have open circuit breakers; reconciliation blocked."
                ),
                context=self._failure_context(reason="all_breakers_open"),
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
                    context=self._failure_context(
                        reason="quota_exhausted",
                        errors=errors,
                        extra={"url": next(iter(errors.keys()), None)},
                    ),
                ) from first

            self._record_outcome(eligible, heights, errors)

            if errors:
                self._last_error = {
                    "layer": "L4",
                    "reason": "reconcile_partial_failure",
                    "failed": {k: str(v) for k, v in errors.items()},
                }

            if len(heights) != len(eligible):
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "One or more RPC endpoints failed during block height reconciliation."
                    ),
                    context=self._failure_context(
                        reason="reconcile_failed",
                        errors=errors,
                        extra={"ok_count": len(heights), "expected": len(eligible)},
                    ),
                )

            values = list(heights.values())
            spread = max(values) - min(values)
            if spread > self.HEALTH_SPREAD_THRESHOLD:
                self._last_error = {
                    "layer": "L4",
                    "reason": "height_spread_exceeded",
                    "heights": dict(heights),
                    "spread": spread,
                    "threshold": self.HEALTH_SPREAD_THRESHOLD,
                }
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "RPC node block heights diverge beyond the allowed threshold; "
                        "treating cluster state as contaminated (fail-closed)."
                    ),
                    context=self._failure_context(
                        reason="height_spread_exceeded",
                        extra={
                            "heights": dict(heights),
                            "spread": spread,
                            "threshold": self.HEALTH_SPREAD_THRESHOLD,
                        },
                    ),
                )

            chosen = min(eligible, key=lambda url: (heights.get(url, 10**18), url))
            self._last_url = chosen
            self._last_selected_latency = None
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
                    context=self._failure_context(
                        reason="quota_exhausted",
                        errors=errors,
                        extra={"url": next(iter(errors.keys()), None)},
                    ),
                ) from first

            self._record_outcome(eligible, heights, errors)

            if len(heights) != len(eligible):
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "One or more RPC endpoints failed during block height reconciliation."
                    ),
                    context=self._failure_context(
                        reason="reconcile_failed",
                        errors=errors,
                        extra={"ok_count": len(heights), "expected": len(eligible)},
                    ),
                )

            values = list(heights.values())
            spread = max(values) - min(values)
            if spread > self.HEALTH_SPREAD_THRESHOLD:
                self._last_error = {
                    "layer": "L4",
                    "reason": "height_spread_exceeded",
                    "heights": dict(heights),
                    "spread": spread,
                    "threshold": self.HEALTH_SPREAD_THRESHOLD,
                }
                raise RPCUnavailableException(
                    human_readable_reason=(
                        "RPC node block heights diverge beyond the allowed threshold; "
                        "treating cluster state as contaminated (fail-closed)."
                    ),
                    context=self._failure_context(
                        reason="height_spread_exceeded",
                        extra={
                            "heights": dict(heights),
                            "spread": spread,
                            "threshold": self.HEALTH_SPREAD_THRESHOLD,
                        },
                    ),
                )

            chosen = min(eligible, key=lambda url: (heights.get(url, 10**18), url))
            self._last_url = chosen
            self._last_selected_latency = None
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


class AsyncQuorumProvider:
    """L4: Multi-source RPC quorum with anti-staleness routing."""

    _RETRYABLE_ERRORS = (ConnectionError, TimeoutError)
    _MAX_RETRIES = 3
    _MAX_BACKOFF_TIME_SEC = 5.0

    def __init__(
        self,
        rpc_urls: List[str],
        *,
        staleness_threshold: int = 2,
        request_timeout: float = 8.0,
        retry_attempts: int = 3,
        retry_base_delay: float = 0.1,
    ) -> None:
        self._rpc_urls = list(rpc_urls)
        self._staleness_threshold = staleness_threshold
        self._timeout = request_timeout
        self._retry_attempts = retry_attempts
        self._retry_base_delay = retry_base_delay
        self._best_url: Optional[str] = None
        self._best_height: Optional[int] = None
        self._last_error: Optional[Dict[str, Any]] = None
        self._last_selected_latency: Optional[float] = None
        self._lock = threading.Lock()

    async def refresh_quorum(self) -> int:
        if not self._rpc_urls:
            self._raise_quorum_failed("rpc_urls is empty")
        outcomes = await asyncio.gather(
            *(self._fetch_block_number(url) for url in self._rpc_urls),
            return_exceptions=True,
        )
        ok_nodes: List[Tuple[str, int, float]] = []
        failures: Dict[str, str] = {}
        for url, outcome in zip(self._rpc_urls, outcomes):
            if isinstance(outcome, BaseException):
                failures[url] = str(outcome)
                continue
            ok_nodes.append(outcome)
        if not ok_nodes:
            self._raise_quorum_failed("all endpoints failed blockNumber", failures=failures)
        head = max(height for _, height, _ in ok_nodes)
        healthy = [
            (url, height, latency)
            for url, height, latency in ok_nodes
            if (head - height) <= self._staleness_threshold
        ]
        if not healthy:
            self._raise_quorum_failed("all endpoints stale", failures=failures)
        best_url, _, best_latency = min(healthy, key=lambda item: (item[2], item[0]))
        self._best_url = best_url
        self._best_height = head
        self._last_selected_latency = best_latency
        return head

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "timeout": self._timeout,
                "best_url": self._best_url,
                "best_height": self._best_height,
                "last_error": dict(self._last_error) if self._last_error is not None else None,
                "rpc_urls": list(self._rpc_urls),
                "rpc_count": len(self._rpc_urls),
                "last_selected_latency": self._last_selected_latency,
                "staleness_threshold": self._staleness_threshold,
            }

    async def eth_call(self, tx: Dict[str, Any], block: str = "latest") -> Any:
        if self._best_url is None:
            await self.refresh_quorum()
        if self._best_url is None:
            self._raise_quorum_failed("no healthy endpoint selected")
        try:
            provider = AsyncHTTPProvider(self._best_url, request_kwargs={"timeout": self._timeout})
            aw3 = AsyncWeb3(provider)
            return await aw3.eth.call(cast(Any, tx), block_identifier=cast(Any, block))
        except BaseException as exc:  # noqa: BLE001
            best_url = cast(str, self._best_url)
            self._raise_quorum_failed(
                "selected endpoint eth_call failed", failures={best_url: str(exc)}
            )

    @property
    def best_url(self) -> Optional[str]:
        return self._best_url

    async def _fetch_block_number(self, url: str) -> Tuple[str, int, float]:
        start = time.perf_counter()
        provider = AsyncHTTPProvider(url, request_kwargs={"timeout": self._timeout})
        aw3 = AsyncWeb3(provider)
        if not await aw3.is_connected():
            raise ConnectionError(f"not connected: {url}")
        height = int(await aw3.eth.block_number)
        latency = time.perf_counter() - start
        return url, height, latency

    @staticmethod
    def _is_quota_exhausted(exc: BaseException) -> bool:
        text = str(exc)
        return "429" in text or "Too Many Requests" in text

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: AsyncQuorumProvider._normalize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [AsyncQuorumProvider._normalize_value(v) for v in value]
        if isinstance(value, tuple):
            return [AsyncQuorumProvider._normalize_value(v) for v in value]
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("0x"):
                hex_body = raw[2:]
                if hex_body == "":
                    return 0
                try:
                    return int(raw, 16)
                except ValueError:
                    return raw.lower()
            return raw
        return value

    @classmethod
    def _serialize_deterministic(cls, result: Any) -> bytes:
        normalized = cls._normalize_value(result)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def _hash_result(cls, result: Any) -> str:
        payload = cls._serialize_deterministic(result)
        return hashlib.sha256(payload).hexdigest()

    async def _retry_call(self, url: str, coro_factory: Any) -> Any:
        delay = self._retry_base_delay
        last_exc: Optional[BaseException] = None
        start = time.perf_counter()
        for attempt in range(self._MAX_RETRIES):
            try:
                return await coro_factory()
            except BaseException as exc:  # noqa: BLE001
                last_exc = exc
                retryable = self._is_quota_exhausted(exc) or isinstance(exc, self._RETRYABLE_ERRORS)
                elapsed = time.perf_counter() - start
                if (
                    (not retryable)
                    or attempt + 1 >= self._MAX_RETRIES
                    or (elapsed + delay) > self._MAX_BACKOFF_TIME_SEC
                ):
                    if isinstance(exc, TimeoutError) or elapsed >= self._MAX_BACKOFF_TIME_SEC:
                        raise LirixRPCTimeoutException(
                            human_readable_reason=(
                                "RPC call timed out while waiting for quorum retries to complete."
                            ),
                            context={"layer": "L4", "url": url, "elapsed_sec": elapsed},
                        ) from exc
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        if last_exc is not None:
            if isinstance(last_exc, TimeoutError):
                raise LirixRPCTimeoutException(
                    human_readable_reason=(
                        "RPC call timed out while waiting for quorum retries to complete."
                    ),
                    context={"layer": "L4", "url": url},
                ) from last_exc
            raise last_exc
        raise RuntimeError(f"unreachable retry state for {url}")

    async def quorum_eth_call(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        if not self._rpc_urls:
            self._last_error = {"layer": "L4", "reason": "rpc_urls_empty"}
            raise LirixConsensusFailureException(
                error_code="LRX_L4_CONSENSUS_FAILED",
                value_protected="RPC Simulation Consistency",
                resolution_agent="No RPC endpoints are configured for quorum simulation.",
                resolution_dev=(
                    "Provide at least one healthy RPC endpoint before invoking quorum_eth_call."
                ),
                context={"layer": "L4", "reason": "rpc_urls_empty"},
            )
        head = await self.refresh_quorum()
        target_block = head - 1
        if target_block < 0:
            self._raise_quorum_failed("latest block height is below 1; cannot pin to N-1")

        async def _call(url: str) -> Tuple[str, Any]:
            async def _do() -> Any:
                provider = AsyncHTTPProvider(url, request_kwargs={"timeout": self._timeout})
                aw3 = AsyncWeb3(provider)
                if not await aw3.is_connected():
                    raise ConnectionError(f"not connected: {url}")
                return await aw3.eth.call(cast(Any, tx), block_identifier=cast(Any, target_block))

            result = await self._retry_call(url, _do)
            return url, result

        results = await asyncio.gather(*(_call(url) for url in self._rpc_urls))

        async def _compute_hash(url: str, res: Any) -> Tuple[str, str]:
            # Force CPU-intensive deterministic serialization + SHA256 offloaded
            # to the system thread pool to avoid blocking the event loop/GIL.
            digest = await asyncio.to_thread(self._hash_result, res)
            return url, digest

        raw: Dict[str, Any] = {url: res for url, res in results}

        hash_tasks = [_compute_hash(url, res) for url, res in results]
        hash_results = await asyncio.gather(*hash_tasks)

        hashes: Dict[str, List[str]] = {}
        url_to_digest: Dict[str, str] = {}
        for url, digest in hash_results:
            url_to_digest[url] = digest
            hashes.setdefault(digest, []).append(url)

        best_hash, nodes = max(hashes.items(), key=lambda item: len(item[1]))
        required_votes = math.ceil(len(self._rpc_urls) * (2 / 3))
        if len(nodes) < required_votes:
            raise LirixConsensusFailureException(
                error_code="LRX_L4_CONSENSUS_FAILED",
                value_protected="RPC Simulation Consistency",
                resolution_agent=(
                    "No dynamic 2/3 quorum was reached across RPC simulation "
                    "results; retry with healthy nodes."
                ),
                resolution_dev=(
                    "Inspect state divergence, endpoint integrity, and latest-block pinning."
                ),
                context={
                    "layer": "L4",
                    "block_number": target_block,
                    "required_votes": required_votes,
                    "observed_votes": len(nodes),
                    "hashes": url_to_digest,
                },
            )
        primary_block_hash = None
        if self._best_url is not None:
            primary_provider = AsyncHTTPProvider(
                self._best_url, request_kwargs={"timeout": self._timeout}
            )
            primary_w3 = AsyncWeb3(primary_provider)
            block_obj = await primary_w3.eth.get_block(target_block)
            primary_block_hash = getattr(block_obj, "hash", None)
        winner_url = nodes[0]
        return {
            "block_number": target_block,
            "block_hash": primary_block_hash,
            "hash": best_hash,
            "result": raw[winner_url],
            "result_source_url": winner_url,
            "winner_url": winner_url,
            "winner_hash": best_hash,
            "quorum": nodes,
            "quorum_size": len(nodes),
            "required_votes": required_votes,
        }

    def quorum_eth_call_sync(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        return asyncio.run(self.quorum_eth_call(tx))

    def _raise_quorum_failed(
        self,
        reason: str,
        *,
        failures: Optional[Dict[str, str]] = None,
    ) -> None:
        context = {
            "layer": "L4",
            "reason": reason,
            "failures": failures or {},
        }
        with self._lock:
            self._last_error = dict(context)
        raise LirixRPCError(
            error_code="LRX_RPC_QUORUM_FAILED",
            value_protected="RPC Availability",
            resolution_agent="Switch RPC quorum source or retry when healthy nodes recover.",
            resolution_dev="Inspect endpoint health, latency, and staleness threshold for quorum.",
            context=context,
        )
