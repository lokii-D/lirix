# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

from lirix.layers.l3_proxy_piercer import AbiLRUCache, ProxyPiercer
from web3 import Web3


class _Eth:
    def __init__(
        self, storage: dict[tuple[str, int], bytes], calls: dict[tuple[str, bytes], Any]
    ) -> None:
        self._storage = storage
        self._calls = calls

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return self._storage.get((Web3.to_checksum_address(address), slot), b"\x00" * 32)

    def call(self, payload: dict[str, Any]) -> Any:
        data = payload["data"]
        key = (
            Web3.to_checksum_address(payload["to"]),
            bytes(data) if isinstance(data, (bytes, bytearray)) else data,
        )
        return self._calls.get(key, b"")


class _W3:
    def __init__(self, eth: _Eth) -> None:
        self.eth = eth


def test_test_proxy_piercer_proxy_piercer_direct_eip1967_paths() -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000aa")
    impl = Web3.to_checksum_address("0x00000000000000000000000000000000000000bb")
    slot = int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16)
    eth = _Eth(storage={(target, slot): b"\x00" * 12 + bytes.fromhex(impl[2:])}, calls={})
    result = ProxyPiercer().inspect_target(_W3(eth), target)
    assert result["proxy_kind"] == "eip1967"
    assert result["resolved_target"] == impl


def test_test_proxy_piercer_proxy_piercer_direct_eip1967_paths_2() -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000cc")
    cache = AbiLRUCache(max_entries=4, ttl_seconds=60, invalidation_interval_seconds=60)
    piercer = ProxyPiercer(abi_cache=cache)
    eth = _Eth(storage={}, calls={})
    fetched = piercer.fetch_abi(_W3(eth), target, abi_fetcher=lambda addr: {"addr": addr})
    assert fetched["cache_hit"] is False
    cached = piercer.fetch_abi(_W3(eth), target, abi_fetcher=lambda addr: {"addr": "miss"})
    assert cached["cache_hit"] is True
    cache.close()


def test_test_proxy_piercer_proxy_piercer_direct_eip1967_paths_3() -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000dd")
    beacon = Web3.to_checksum_address("0x00000000000000000000000000000000000000be")
    uups = Web3.to_checksum_address("0x00000000000000000000000000000000000000ee")
    slot_implementation = int(
        "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16
    )
    slot_beacon = int("0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50", 16)
    slot_uups = int("0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876bb1f7c97", 16)
    eth = _Eth(
        storage={
            (target, slot_beacon): b"\x00" * 12 + bytes.fromhex(beacon[2:]),
            (target, slot_implementation): b"\x00" * 32,
            (target, slot_uups): b"\x00" * 12 + bytes.fromhex(uups[2:]),
        },
        calls={(beacon, bytes.fromhex("5c60da1b")): b""},
    )
    result = ProxyPiercer().inspect_target(_W3(eth), target)
    assert result["proxy_kind"] == "beacon_unresolved"
    assert result["resolved_target"] == uups
    assert "fallback.eip1822_uups" in result["resolution_path"]
