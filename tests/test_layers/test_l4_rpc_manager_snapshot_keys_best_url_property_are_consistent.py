# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_snapshot_keys_best_url_property_are_consistent() -> None:
    provider = AsyncQuorumProvider(["u1"])
    snap = provider.snapshot()
    assert "rpc_count" in snap and snap["rpc_count"] == 1
    assert provider.best_url is None
