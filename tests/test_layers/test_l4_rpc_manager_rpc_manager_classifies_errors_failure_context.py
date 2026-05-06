# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, RPCManager


class _Cfg(LirixConfig):
    pass


def _config() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=["https://a.invalid", "https://b.invalid"],
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x0000000000000000000000000000000000000001"],
    )


def test_test_l4_rpc_manager_rpc_manager_classifies_errors_failure_context() -> None:
    mgr = RPCManager(_config())
    errs: dict[str, BaseException] = {
        "https://a.invalid": TimeoutError("timeout"),
        "https://b.invalid": ConnectionError("conn"),
    }
    classified = mgr._classify_errors(errs)
    assert classified["timeout"] == ["https://a.invalid"]
    assert classified["transport"] == ["https://b.invalid"]
    ctx = mgr._failure_context(reason="reconcile_failed", errors=errs, extra={"ok_count": 0})
    assert ctx["reason"] == "reconcile_failed"
    assert ctx["classified"]["timeout"] == ["https://a.invalid"]
    assert ctx["ok_count"] == 0


def test_test_l4_rpc_manager_rpc_manager_classifies_errors_failure_context_2() -> None:
    result = {"a": "0x10", "b": [" 0x01 ", ("x", "0x")], "c": "Hello"}
    digest1 = AsyncQuorumProvider._hash_result(result)
    digest2 = AsyncQuorumProvider._hash_result(
        {"c": "Hello", "b": ["0x01", ("x", "0x")], "a": "0x10"}
    )
    assert digest1 == digest2
    assert AsyncQuorumProvider._normalize_value(result)["a"] == 16
    assert AsyncQuorumProvider._normalize_value(result)["b"][0] == 1
