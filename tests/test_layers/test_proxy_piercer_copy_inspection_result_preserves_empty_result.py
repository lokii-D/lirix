# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_copy_inspection_result_preserves_empty_result() -> None:
    copied = ProxyPiercer._copy_inspection_result({})
    assert copied == {}
