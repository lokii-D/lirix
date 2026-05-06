# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

from lirix.layers.l3_proxy_piercer import ProxyPiercer
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


def _slot_bytes(addr: str) -> bytes:
    return b"\x00" * 12 + bytes.fromhex(addr[2:])


def test_test_proxy_piercer_proxy_piercer_prefers_cache_copy_fetch_abi_cache() -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000ef")
    impl = Web3.to_checksum_address("0x00000000000000000000000000000000000000aa")
    storage = {
        (
            target,
            int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16),
        ): _slot_bytes(impl)
    }
    piercer = ProxyPiercer()
    web3 = _W3(_Eth(storage, {}))
    abi_seen: list[Any] = []

    def fetcher(addr: str) -> Any:
        abi_seen.append(addr)
        return [{"type": "function", "name": "f"}]

    first = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)
    first["proxy"]["resolution_path"].append("mutated")
    second = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)
    assert abi_seen == [impl]
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert second["proxy"]["resolution_path"] == ["eip1967_implementation"]


def test_test_proxy_piercer_proxy_piercer_prefers_cache_copy_fetch_abi_cache_2() -> None:
    piercer = ProxyPiercer()
    snap = piercer.snapshot()
    assert snap["inspection_cache_entries"] == 0
    assert snap["inspection_cache_max_entries"] >= 1
