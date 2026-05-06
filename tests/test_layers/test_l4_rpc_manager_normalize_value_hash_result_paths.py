# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_normalize_value_hash_result_paths() -> None:
    normalized = AsyncQuorumProvider._normalize_value({"a": ["0x1", ("0x2",)], "b": " hello "})
    assert normalized == {"a": [1, [2]], "b": "hello"}
    assert len(AsyncQuorumProvider._hash_result({"x": 1})) == 64
