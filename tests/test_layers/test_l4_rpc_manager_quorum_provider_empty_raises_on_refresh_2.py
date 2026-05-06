# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio

import pytest
from lirix.core.exceptions import LirixRPCError
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_quorum_provider_empty_raises_on_refresh_2() -> None:
    provider = AsyncQuorumProvider([])
    with pytest.raises(LirixRPCError, match="LRX_RPC_QUORUM_FAILED"):
        asyncio.run(provider.refresh_quorum())
