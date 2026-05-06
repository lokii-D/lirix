# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_hash_result_is_deterministic_for_nested_structures() -> None:
    a = AsyncQuorumProvider._hash_result({"b": [1, 2], "a": {"x": "0x1"}})
    b = AsyncQuorumProvider._hash_result({"a": {"x": 1}, "b": [1, 2]})
    assert len(a) == 64
    assert a == b
