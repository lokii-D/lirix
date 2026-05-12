# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio

import pytest
from lirix.core.exceptions import LirixRPCError
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_quorum_provider_empty_refresh_raises_rpc_error() -> None:
    provider = AsyncQuorumProvider([])
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        asyncio.run(provider.refresh_quorum())


def test_quorum_provider_empty_snapshot_has_no_best_url() -> None:
    provider = AsyncQuorumProvider([])
    assert provider.best_url is None
    snap = provider.snapshot()
    assert snap["best_url"] is None
    assert snap["rpc_count"] == 0
