# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_snapshot_copy_result_stable() -> None:
    piercer = ProxyPiercer()
    snap = piercer.snapshot()
    assert isinstance(snap, dict)
    copied = ProxyPiercer._copy_inspection_result({"a": 1})
    assert copied == {"a": 1}
