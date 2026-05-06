# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_allows_plain_dicts() -> None:
    result = {"a": 1, "b": {"c": 2}}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied == result
