from __future__ import annotations

from pathlib import Path

import pytest
from lirix.layers.l3_proxy_piercer import AbiLRUCache
from web3 import Web3


def test_test_proxy_piercer_abi_cache_get_purges_stale_memory_entry(tmp_path: Path) -> None:
    now = 100
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi-cache.sqlite3"),
        ttl_seconds=5,
        invalidation_interval_seconds=60,
        time_fn=lambda: now,
    )
    address = "0x00000000000000000000000000000000000000A1"
    cache.set(address, [{"name": "f"}])

    now = 106
    assert cache.get(address) is None
    assert cache.snapshot()["memory_entries"] == 0
    cache.close()


def test_test_proxy_piercer_abi_cache_get_purges_stale_memory_entry_2(tmp_path: Path) -> None:
    now = 200
    db_path = tmp_path / "abi-cache.sqlite3"
    cache = AbiLRUCache(
        sqlite_path=str(db_path),
        ttl_seconds=50,
        invalidation_interval_seconds=60,
        time_fn=lambda: now,
    )
    address = "0x00000000000000000000000000000000000000B2"
    cache.set(address, [{"name": "g"}])
    cache._memory.clear()  # force DB read path

    loaded = cache.get(address)
    assert loaded == [{"name": "g"}]
    cache.close()


def test_test_proxy_piercer_abi_cache_get_purges_stale_memory_entry_3() -> None:
    payload = {"handler": lambda x: x}
    copied = AbiLRUCache._copy_cached_abi(payload)
    assert copied is payload


def test_test_proxy_piercer_abi_cache_get_purges_stale_memory_entry_4(tmp_path: Path) -> None:
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi-cache.sqlite3"),
        ttl_seconds=5,
        invalidation_interval_seconds=60,
    )
    cache.close()
    snapshot = cache.snapshot()
    assert snapshot["closed"] is True

    with pytest.raises(RuntimeError, match="AbiLRUCache is closed"):
        cache.invalidate("0x00000000000000000000000000000000000000C3")


def test_test_proxy_piercer_abi_cache_get_purges_stale_memory_entry_5(tmp_path: Path) -> None:
    now = 300
    db_path = tmp_path / "abi-cache.sqlite3"
    cache = AbiLRUCache(
        sqlite_path=str(db_path),
        ttl_seconds=2,
        invalidation_interval_seconds=60,
        time_fn=lambda: now,
    )
    address = Web3.to_checksum_address("0x00000000000000000000000000000000000000D4")
    cache.set(address, [{"name": "h"}])

    now = 305
    cache.invalidate_stale()

    row = cache._db.execute(
        "SELECT address FROM abi_cache WHERE address = ?", (address,)
    ).fetchone()
    assert row is None
    cache.close()
