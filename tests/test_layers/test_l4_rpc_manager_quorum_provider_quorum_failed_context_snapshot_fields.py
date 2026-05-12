# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l4_rpc_manager import AsyncQuorumProvider


def test_test_l4_rpc_manager_quorum_provider_quorum_failed_context_snapshot_fields() -> None:
    provider = AsyncQuorumProvider(["u1"])
    provider._last_error = {"layer": "L4", "reason": "boom"}  # noqa: SLF001
    snap = provider.snapshot()
    assert snap["path_role"] == AsyncQuorumProvider.PATH_ROLE
    assert "secondary compatibility path" in snap["usage_warning"]
    assert snap["rpc_count"] == 1
    assert snap["last_error"]["reason"] == "boom"
