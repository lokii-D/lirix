# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_snapshot_reports_cache_shape_result_copying() -> None:
    piercer = ProxyPiercer()
    snap = piercer.snapshot()
    assert "inspection_cache_entries" in snap
    assert "inspection_cache_max_entries" in snap
    assert ProxyPiercer._copy_inspection_result({"resolution_path": ["x"], "nested": {"a": 1}})[
        "nested"
    ] == {"a": 1}
