# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.layers.l3_proxy_piercer import ProxyPiercer
from web3 import Web3


class _FakeEth:
    def __init__(self, responses: dict[tuple[str, int] | tuple[str, str], Any]) -> None:
        self._responses = responses

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return self._responses.get((address, slot), b"\x00" * 32)

    def call(self, payload: dict[str, Any]) -> Any:
        data = payload["data"]
        if isinstance(data, (bytes, bytearray)):
            data_key: Any = bytes(data)
        else:
            data_key = data
        key = (Web3.to_checksum_address(payload["to"]), data_key)
        return self._responses.get(key, b"")


class _FakeWeb3:
    def __init__(self, eth: _FakeEth) -> None:
        self.eth = eth


def _slot_bytes(addr: str) -> bytes:
    return b"\x00" * 12 + bytes.fromhex(addr[2:])


def test_test_proxy_piercer() -> None:
    target = Web3.to_checksum_address("0x000000000000000000000000000000000000d1a9")
    facet = Web3.to_checksum_address("0x000000000000000000000000000000000000fAce")
    responses = {
        (target, 0): b"\x00" * 32,
        (target, 1): b"\x00" * 32,
        (target, 2): b"\x00" * 32,
        (target, 3): b"\x00" * 32,
        (target, bytes.fromhex("cdffacc6")): _slot_bytes(facet),
    }
    web3 = _FakeWeb3(_FakeEth(responses))
    result = ProxyPiercer().inspect_target(web3, target)
    assert result["proxy_kind"] == "diamond"
    assert result["resolved_target"] == facet
    assert "eip2535_diamond" in result["resolution_path"]


def test_test_proxy_piercer_2(monkeypatch: pytest.MonkeyPatch) -> None:
    target = Web3.to_checksum_address("0x000000000000000000000000000000000000bEac")
    beacon = Web3.to_checksum_address("0x000000000000000000000000000000000000bE01")
    implementation = Web3.to_checksum_address("0x000000000000000000000000000000000000bE02")
    responses = {
        (
            target,
            int("0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103", 16),
        ): b"\x00"
        * 32,
        (
            target,
            int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16),
        ): b"\x00"
        * 32,
        (
            target,
            int("0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50", 16),
        ): _slot_bytes(beacon),
        (
            target,
            int("0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876bb1f7c97", 16),
        ): b"\x00"
        * 32,
        (beacon, "0x5c60da1b"): _slot_bytes(implementation),
        (beacon, bytes.fromhex("5c60da1b")): _slot_bytes(implementation),
    }
    web3 = _FakeWeb3(_FakeEth(responses))
    piercer = ProxyPiercer()
    first = piercer.inspect_target(web3, target)
    assert first["proxy_kind"] == "beacon"
    assert first["resolved_target"] == implementation
    second = piercer.inspect_target(web3, target)
    assert second == first


def test_test_proxy_piercer_3(monkeypatch: pytest.MonkeyPatch) -> None:
    target = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")
    web3 = _FakeWeb3(
        _FakeEth(
            {
                (target, 0): b"\x00" * 32,
                (target, 1): b"\x00" * 32,
                (target, 2): b"\x00" * 32,
                (target, 3): b"\x00" * 32,
            }
        )
    )
    piercer = ProxyPiercer()
    calls: list[str] = []

    def fetcher(addr: str) -> list[dict[str, str]]:
        calls.append(addr)
        return [{"name": addr}]

    first = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)
    second = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert calls == [target]


def test_test_proxy_piercer_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    web3 = _FakeWeb3(
        _FakeEth(
            {
                (target, 0): b"\x00" * 32,
                (target, 1): b"\x00" * 32,
                (target, 2): b"\x00" * 32,
                (target, 3): b"\x00" * 32,
            }
        )
    )
    piercer = ProxyPiercer()
    monkeypatch.setattr(
        ProxyPiercer, "_resolve_diamond_facet", classmethod(lambda cls, w3, t: None)
    )
    assert piercer.resolve_implementation(web3, target) == target
