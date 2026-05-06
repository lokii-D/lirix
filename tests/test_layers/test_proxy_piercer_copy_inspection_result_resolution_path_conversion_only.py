# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_resolution_path_conversion_only() -> None:
    result = {"resolution_path": ("eip1967", "fallback"), "x": 1}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["resolution_path"] == ["eip1967", "fallback"]
    assert copied["x"] == 1
