# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_retry_call_non_retryable_quorum_failed_context() -> None:
    provider = AsyncQuorumProvider(["u1"])

    async def bad():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(provider._retry_call("u1", bad))
