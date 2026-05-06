# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_is_quota_exhausted_normalize_tuple() -> None:
    assert AsyncQuorumProvider._is_quota_exhausted(RuntimeError("429 Too Many Requests")) is True
    assert AsyncQuorumProvider._normalize_value(("0x1", "x")) == [1, "x"]
