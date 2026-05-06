# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, RPCManager


def test_test_l4_rpc_manager_async_quorum_provider_normalize_serialize_tuple_nested_hex() -> None:
    payload = {
        "outer": ("0x01", ["0x0", {"inner": " 0x0A "}]),
        "plain": " keep-me ",
        "empty": "0x",
    }
    normalized = AsyncQuorumProvider._normalize_value(payload)
    assert normalized == {"outer": [1, [0, {"inner": 10}]], "plain": "keep-me", "empty": 0}
    assert AsyncQuorumProvider._hash_result(payload) == AsyncQuorumProvider._hash_result(payload)


def test_test_l4_rpc_manager_async_quorum_provider_normalize_serialize_tuple_nested_hex_2() -> None:
    cfg = LirixConfig(chain_id=1, rpc_urls=["http://a:8545", "http://b:8545"])
    mgr = RPCManager(cfg)
    mgr._failures["http://a:8545"] = 2  # noqa: SLF001
    mgr._open["http://b:8545"] = True  # noqa: SLF001
    mgr._cooldown_until["http://b:8545"] = 123.0  # noqa: SLF001
    mgr._last_url = "http://a:8545"  # noqa: SLF001
    mgr._last_selected_latency = 1.23  # noqa: SLF001

    ctx = mgr._failure_context(
        reason="quota_exhausted",
        errors={"http://a:8545": ConnectionError("HTTP 429 Too Many Requests")},
        extra={"note": "x"},
    )

    assert ctx["reason"] == "quota_exhausted"
    assert ctx["health"]["last_url"] == "http://a:8545"
    assert ctx["health"]["eligible_count"] == 1
    assert ctx["classified"]["quota_exhausted"] == ["http://a:8545"]
    assert ctx["note"] == "x"
