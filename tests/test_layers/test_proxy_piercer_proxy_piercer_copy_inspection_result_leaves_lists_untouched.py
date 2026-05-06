# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_proxy_piercer_copy_inspection_result_leaves_lists_untouched() -> None:
    res = {"resolution_path": ["a", "b"], "x": 1}
    copied = ProxyPiercer._copy_inspection_result(res)
    assert copied["resolution_path"] == ["a", "b"]
    assert copied["x"] == 1
