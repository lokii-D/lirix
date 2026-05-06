# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

from lirix.layers.l3_proxy_piercer import ProxyPiercer
from web3 import Web3


class _Eth:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return b"\x00" * 32

    def call(self, payload: dict[str, Any]) -> bytes:
        self.calls.append(payload)
        data = payload["data"]
        if isinstance(data, (bytes, bytearray)) and bytes(data).hex() == "cdffacc6":
            return b"\x00" * 12 + bytes.fromhex("00000000000000000000000000000000000000ff")
        return b""


class _W3:
    def __init__(self) -> None:
        self.eth = _Eth()


def test_test_proxy_piercer_proxy_piercer_diamond_resolution_copy_semantics() -> None:
    target = Web3.to_checksum_address("0x0000000000000000000000000000000000000d1a")
    web3 = _W3()
    piercer = ProxyPiercer()
    result = piercer.inspect_target(web3, target)
    assert result["proxy_kind"] == "diamond"
    assert result["resolved_target"] == Web3.to_checksum_address(
        "0x00000000000000000000000000000000000000ff"
    )
    result["resolution_path"].append("mutated")
    second = piercer.inspect_target(web3, target)
    assert second["resolution_path"] == ["eip2535_diamond"]
    assert second["resolved_target"] == Web3.to_checksum_address(
        "0x00000000000000000000000000000000000000ff"
    )
