# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_keeps_non_resolution_path_fields() -> None:
    result = {"resolution_path": ("a", "b"), "admin": "0x1", "nested": {"x": 1}}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["admin"] == "0x1"
    assert copied["nested"] == {"x": 1}
