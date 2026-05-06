# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_nested_dict_passthrough() -> None:
    result = {"resolution_path": ["eip1967"], "nested": {"a": 1}, "x": 1}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["nested"] == {"a": 1}
    assert copied["resolution_path"] == ["eip1967"]
