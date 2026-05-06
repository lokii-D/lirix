# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

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
