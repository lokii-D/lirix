# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_snapshot_has_consistent_shape() -> None:
    provider = AsyncQuorumProvider(["u1", "u2"])
    snap = provider.snapshot()
    assert set(snap.keys()) >= {
        "timeout",
        "best_url",
        "best_height",
        "last_error",
        "rpc_urls",
        "rpc_count",
        "last_selected_latency",
        "staleness_threshold",
    }
