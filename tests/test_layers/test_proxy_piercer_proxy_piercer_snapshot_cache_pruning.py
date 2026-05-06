# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

from lirix.layers.l3_proxy_piercer import ProxyPiercer


class _Eth:
    def __init__(self, call_result: bytes | str | None = None) -> None:
        self._call_result = call_result

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return b"\x00" * 32

    def call(self, payload: Any) -> bytes | str | None:
        return self._call_result


class _Web3:
    def __init__(self, call_result: bytes | str | None = None) -> None:
        self.eth = _Eth(call_result)


def test_test_proxy_piercer_proxy_piercer_snapshot_cache_pruning() -> None:
    piercer = ProxyPiercer()
    snap = piercer.snapshot()
    assert "inspection_cache_entries" in snap
    assert snap["inspection_cache_max_entries"] >= 1
