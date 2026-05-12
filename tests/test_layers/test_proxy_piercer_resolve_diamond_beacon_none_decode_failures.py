# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

from lirix.layers.l3_proxy_piercer import ProxyPiercer
from web3 import Web3


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


def test_proxy_piercer_returns_none_on_diamond_beacon_and_decode_failures() -> None:
    piercer = ProxyPiercer()
    assert (
        piercer._resolve_diamond_facet(
            _Web3(b""), Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
        )
        is None
    )
    assert (
        piercer._resolve_beacon_implementation(
            _Web3("0x1234"), Web3.to_checksum_address("0x0000000000000000000000000000000000000002")
        )
        is None
    )
    assert piercer._decode_abi_address(_Web3(), b"\x00" * 32) is None
