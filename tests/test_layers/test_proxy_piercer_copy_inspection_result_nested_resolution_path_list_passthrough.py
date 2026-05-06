# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_nested_resolution_path_list_passthrough() -> (
    None
):
    res = {"resolution_path": [["a"]], "x": 1}
    copied = ProxyPiercer._copy_inspection_result(res)
    assert copied["resolution_path"] == [["a"]]
