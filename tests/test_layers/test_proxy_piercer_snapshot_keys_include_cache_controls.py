# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_snapshot_keys_include_cache_controls() -> None:
    snap = ProxyPiercer().snapshot()
    assert "inspection_cache_entries" in snap
    assert "inspection_cache_ttl_seconds" in snap
