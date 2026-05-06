# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_quorum_provider_empty_best_url_snapshot() -> None:
    provider = AsyncQuorumProvider([])
    assert provider.best_url is None
    snap = provider.snapshot()
    assert snap["best_url"] is None
    assert snap["rpc_count"] == 0
