# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.layers.l3_proxy_piercer import AbiLRUCache, ProxyPiercer
from web3 import Web3


class _Eth:
    def __init__(
        self, storage_map: dict[tuple[str, int], bytes], call_result: bytes | str | None = None
    ) -> None:
        self._storage_map = storage_map
        self._call_result = call_result

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return self._storage_map.get((address, slot), b"\x00" * 32)

    def call(self, payload):
        return self._call_result or b""


class _Web3:
    def __init__(
        self, storage_map: dict[tuple[str, int], bytes], call_result: bytes | str | None = None
    ) -> None:
        self.eth = _Eth(storage_map, call_result)


def test_test_proxy_piercer_proxy_piercer_read_slot_cache_close_paths(tmp_path) -> None:
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi.db"), ttl_seconds=1, invalidation_interval_seconds=1
    )
    piercer = ProxyPiercer(abi_cache=cache)
    target = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    impl = Web3.to_checksum_address("0x0000000000000000000000000000000000000002")
    storage = {
        (
            target,
            int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16),
        ): bytes.fromhex("00" * 12 + impl[2:])
    }
    web3 = _Web3(storage)
    assert (
        ProxyPiercer._read_slot_address(
            web3,
            target,
            int("0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc", 16),
        )
        == impl
    )
    out = piercer.fetch_abi(web3, target, abi_fetcher=lambda addr: ["abi"])
    assert out["cache_hit"] is False
    cache.close()
    with pytest.raises(RuntimeError, match="AbiLRUCache is closed"):
        cache.get(target)
