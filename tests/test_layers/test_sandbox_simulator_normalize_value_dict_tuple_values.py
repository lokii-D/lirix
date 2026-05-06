# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_sandbox_simulator_normalize_value_dict_tuple_values() -> None:
    payload = AsyncQuorumProvider._normalize_value({"a": ["0x1", ("0x2",)]})
    assert payload == {"a": [1, [2]]}
