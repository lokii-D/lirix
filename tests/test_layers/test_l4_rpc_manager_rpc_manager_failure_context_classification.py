# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixRPCTimeoutException, RPCManager


def test_test_l4_rpc_manager_rpc_manager_failure_context_classification() -> None:
    config = LirixConfig(chain_id=1, rpc_urls=["https://a", "https://b"])
    manager = RPCManager(config)
    ctx = manager._failure_context(
        reason="reconcile_failed",
        errors={"https://a": ConnectionError("boom"), "https://b": TimeoutError("slow")},
        extra={"ok_count": 1},
    )
    assert ctx["reason"] == "reconcile_failed"
    assert ctx["classified"]["transport"] == ["https://a"]
    assert ctx["classified"]["timeout"] == ["https://b"]
    assert ctx["ok_count"] == 1


def test_test_l4_rpc_manager_rpc_manager_failure_context_classification_2() -> None:
    value = {"b": ["0x01", (" 0x02 ",)], "a": "  hello  "}
    assert AsyncQuorumProvider._normalize_value(value) == {"b": [1, [2]], "a": "hello"}
    digest_a = AsyncQuorumProvider._hash_result(value)
    digest_b = AsyncQuorumProvider._hash_result({"a": "hello", "b": ["0x01", ("0x02",)]})
    assert digest_a == digest_b


def test_test_l4_rpc_manager_rpc_manager_failure_context_classification_3(monkeypatch) -> None:
    provider = AsyncQuorumProvider(["https://a"], request_timeout=1, retry_attempts=1)

    async def boom() -> None:
        raise TimeoutError("slow")

    monkeypatch.setattr(provider, "_MAX_RETRIES", 1)
    try:
        import asyncio

        asyncio.run(provider._retry_call("https://a", boom))
    except LirixRPCTimeoutException as exc:
        assert exc.context["url"] == "https://a"
