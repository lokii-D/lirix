# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_missing_resolution_path_passthrough() -> None:
    res = {"x": 1}
    copied = ProxyPiercer._copy_inspection_result(res)
    assert copied == res
