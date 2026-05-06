# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import TxParams

try:
    from eth_abi.abi import decode as _abi_decode
except ImportError:  # pragma: no cover - optional dependency fallback
    abi_decode: Optional[Callable[[List[str], bytes], tuple[Any, ...]]] = None
else:
    abi_decode = _abi_decode

EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
EIP1822_PROXIABLE_SLOT = "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876bb1f7c97"
BEACON_IMPLEMENTATION_SELECTOR = "0x5c60da1b"
DIAMOND_FACET_ADDRESS_SELECTOR = "0xcdffacc6"  # facetAddress(bytes4)


class AbiLRUCache:
    """Hybrid ABI cache: in-memory LRU + SQLite persistence."""

    def __init__(
        self,
        *,
        max_entries: int = 256,
        sqlite_path: Optional[str] = None,
        ttl_seconds: int = 24 * 60 * 60,
        invalidation_interval_seconds: int = 60,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._invalidation_interval_seconds = max(1, invalidation_interval_seconds)
        self._time_fn = time_fn or time.time
        self._lock = threading.Lock()
        self._memory: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        db_path = sqlite_path or ":memory:"
        if db_path != ":memory:":
            normalized_db_path = Path(db_path).expanduser().resolve()
            normalized_db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path = str(normalized_db_path)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS abi_cache (
                address TEXT PRIMARY KEY,
                abi_json TEXT NOT NULL,
                touched_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        self._db.commit()
        self._stop_event = threading.Event()
        self._closed = False
        self._last_touch_at: Dict[str, int] = {}
        self._janitor = threading.Thread(target=self._invalidation_loop, daemon=True)
        self._janitor.start()

    def get(self, address: str) -> Optional[Any]:
        key = Web3.to_checksum_address(address)
        with self._lock:
            self._ensure_open_locked()
            if key in self._memory:
                entry = self._memory.pop(key)
                if self._is_stale(entry["expires_at"]):
                    self._purge_locked(key)
                    return None
                self._memory[key] = entry
                self._touch_locked(key)
                return entry["abi"]
            row = self._db.execute(
                "SELECT abi_json, expires_at, touched_at FROM abi_cache WHERE address = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            expires_at = int(row[1])
            if self._is_stale(expires_at):
                self._purge_locked(key)
                return None
            value = json.loads(str(row[0]))
            self._memory[key] = {"abi": value, "expires_at": expires_at}
            self._trim_memory_locked()
            self._touch_locked(key, touched_at=int(row[2]))
            return value

    def set(self, address: str, abi: Any) -> None:
        key = Web3.to_checksum_address(address)
        encoded = json.dumps(abi, separators=(",", ":"))
        now = self._now()
        expires_at = now + self._ttl_seconds
        with self._lock:
            self._ensure_open_locked()
            if key in self._memory:
                self._memory.pop(key)
            self._memory[key] = {"abi": self._copy_cached_abi(abi), "expires_at": expires_at}
            self._trim_memory_locked()
            self._touch_locked(key, touched_at=now)
            self._db.execute(
                """
                INSERT INTO abi_cache(address, abi_json, touched_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE
                SET abi_json = excluded.abi_json,
                    touched_at = excluded.touched_at,
                    expires_at = excluded.expires_at
                """,
                (key, encoded, now, expires_at),
            )
            self._db.commit()

    def invalidate(self, address: str) -> None:
        key = Web3.to_checksum_address(address)
        with self._lock:
            self._ensure_open_locked()
            self._purge_locked(key)

    def invalidate_stale(self) -> None:
        with self._lock:
            self._ensure_open_locked()
            self._invalidate_stale_locked()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop_event.set()
        self._janitor.join(timeout=1.0)
        with self._lock:
            self._db.close()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._ensure_open_locked(allow_closed=True)
            now = self._now()
            stale_count = sum(
                1 for entry in self._memory.values() if int(entry["expires_at"]) <= now
            )
            return {
                "max_entries": self._max_entries,
                "memory_entries": len(self._memory),
                "stale_entries": stale_count,
                "ttl_seconds": self._ttl_seconds,
                "invalidation_interval_seconds": self._invalidation_interval_seconds,
                "closed": self._closed,
            }

    def _trim_memory_locked(self) -> None:
        while len(self._memory) > self._max_entries:
            self._memory.popitem(last=False)

    def _invalidate_stale_locked(self) -> None:
        now = self._now()
        stale_keys = [key for key, entry in self._memory.items() if int(entry["expires_at"]) <= now]
        for key in stale_keys:
            self._memory.pop(key, None)
        rows = self._db.execute(
            "SELECT address FROM abi_cache WHERE expires_at <= ?",
            (now,),
        ).fetchall()
        if rows:
            self._db.execute("DELETE FROM abi_cache WHERE expires_at <= ?", (now,))
            self._db.commit()

    def _invalidation_loop(self) -> None:
        while not self._stop_event.wait(self._invalidation_interval_seconds):
            with self._lock:
                if self._closed:
                    return
                self._invalidate_stale_locked()

    def _touch_locked(self, address: str, *, touched_at: Optional[int] = None) -> None:
        now = self._now() if touched_at is None else int(touched_at)
        last = self._last_touch_at.get(address)
        if last is not None and (now - last) < self._invalidation_interval_seconds:
            return
        self._last_touch_at[address] = now
        self._db.execute("UPDATE abi_cache SET touched_at = ? WHERE address = ?", (now, address))
        self._db.commit()

    @staticmethod
    def _copy_cached_abi(abi: Any) -> Any:
        try:
            return json.loads(json.dumps(abi, separators=(",", ":")))
        except Exception:
            return abi

    def _ensure_open_locked(self, allow_closed: bool = False) -> None:
        if self._closed and not allow_closed:
            raise RuntimeError("AbiLRUCache is closed")

    def _purge_locked(self, address: str) -> None:
        self._memory.pop(address, None)
        self._last_touch_at.pop(address, None)
        self._db.execute("DELETE FROM abi_cache WHERE address = ?", (address,))
        self._db.commit()

    def _is_stale(self, expires_at: int) -> bool:
        return int(expires_at) <= self._now()

    def _now(self) -> int:
        return int(self._time_fn())


class ProxyPiercer:
    """Resolve proxy targets across EIP-1967, Beacon, and EIP-1822."""

    INSPECTION_CACHE_TTL_SECONDS: int = 60
    INSPECTION_CACHE_MAX_ENTRIES: int = 256

    def __init__(self, *, abi_cache: Optional[AbiLRUCache] = None) -> None:
        self._cache = abi_cache or AbiLRUCache()
        self._inspection_cache: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self._inspection_lock = threading.Lock()
        self._implementation_slot = int(EIP1967_IMPLEMENTATION_SLOT, 16)
        self._beacon_slot = int(EIP1967_BEACON_SLOT, 16)
        self._admin_slot = int(EIP1967_ADMIN_SLOT, 16)
        self._uups_slot = int(EIP1822_PROXIABLE_SLOT, 16)

    def resolve_implementation(self, web3: Web3, target_address: str) -> str:
        return str(self.inspect_target(web3, target_address)["resolved_target"])

    def inspect_target(self, web3: Web3, target_address: str) -> Dict[str, Any]:
        target = Web3.to_checksum_address(target_address)
        now = time.time()
        with self._inspection_lock:
            cached = self._inspection_cache.get(target)
            if cached is not None:
                expires_at, cached_result = cached
                if now < expires_at:
                    self._inspection_cache.move_to_end(target)
                    return self._copy_inspection_result(cached_result)
                self._inspection_cache.pop(target, None)

        admin = self._read_slot_address(web3, target, self._admin_slot)
        implementation = self._read_slot_address(web3, target, self._implementation_slot)
        beacon = self._read_slot_address(web3, target, self._beacon_slot)
        uups = self._read_slot_address(web3, target, self._uups_slot)
        resolution_path: List[str] = []

        if beacon is not None:
            resolution_path.append("eip1967_beacon")
            beacon_implementation = self._resolve_beacon_implementation(web3, beacon)
            resolved = beacon_implementation or implementation or uups or target
            proxy_kind = "beacon" if beacon_implementation is not None else "beacon_unresolved"
            if beacon_implementation is not None:
                resolution_path.append("beacon.implementation()")
            else:
                if implementation is not None:
                    resolution_path.append("fallback.eip1967_implementation")
                elif uups is not None:
                    resolution_path.append("fallback.eip1822_uups")
                else:
                    resolution_path.append("fallback.self")
            result = {
                "target": target,
                "resolved_target": resolved,
                "proxy_kind": proxy_kind,
                "implementation": implementation,
                "beacon": beacon,
                "beacon_implementation": beacon_implementation,
                "admin": admin,
                "uups_implementation": uups,
                "is_proxy": True,
                "resolution_path": resolution_path,
            }
            self._store_inspection_cache(target, result, now)
            return self._copy_inspection_result(result)

        if implementation is not None:
            resolution_path.append("eip1967_implementation")
            result = {
                "target": target,
                "resolved_target": implementation,
                "proxy_kind": "eip1967",
                "implementation": implementation,
                "beacon": beacon,
                "beacon_implementation": None,
                "admin": admin,
                "uups_implementation": uups,
                "is_proxy": True,
                "resolution_path": resolution_path,
            }
            self._store_inspection_cache(target, result, now)
            return self._copy_inspection_result(result)

        if uups is not None:
            resolution_path.append("eip1822_uups")
            result = {
                "target": target,
                "resolved_target": uups,
                "proxy_kind": "uups",
                "implementation": None,
                "beacon": beacon,
                "beacon_implementation": None,
                "admin": admin,
                "uups_implementation": uups,
                "is_proxy": True,
                "resolution_path": resolution_path,
            }
            self._store_inspection_cache(target, result, now)
            return self._copy_inspection_result(result)

        diamond = self._resolve_diamond_facet(web3, target)
        if diamond is not None:
            resolution_path.append("eip2535_diamond")
            result = {
                "target": target,
                "resolved_target": diamond,
                "proxy_kind": "diamond",
                "implementation": diamond,
                "beacon": beacon,
                "beacon_implementation": None,
                "admin": admin,
                "uups_implementation": None,
                "is_proxy": True,
                "resolution_path": resolution_path,
            }
            self._store_inspection_cache(target, result, now)
            return self._copy_inspection_result(result)

        if admin is not None:
            resolution_path.append("eip1967_admin")
        result = {
            "target": target,
            "resolved_target": target,
            "proxy_kind": "direct" if admin is None else "admin_only_proxy",
            "implementation": None,
            "beacon": None,
            "beacon_implementation": None,
            "admin": admin,
            "uups_implementation": None,
            "is_proxy": admin is not None,
            "resolution_path": resolution_path,
        }
        self._store_inspection_cache(target, result, now)
        return self._copy_inspection_result(result)

    def _store_inspection_cache(self, target: str, result: Dict[str, Any], now: float) -> None:
        expires_at = now + self.INSPECTION_CACHE_TTL_SECONDS
        with self._inspection_lock:
            cached_result = self._copy_inspection_result(result)
            self._inspection_cache[target] = (expires_at, cached_result)
            self._inspection_cache.move_to_end(target)
            self._purge_stale_inspection_cache_locked(now)
            while len(self._inspection_cache) > self.INSPECTION_CACHE_MAX_ENTRIES:
                self._inspection_cache.popitem(last=False)

    def _purge_stale_inspection_cache_locked(self, now: float) -> None:
        stale_keys = [
            key for key, (expires_at, _) in self._inspection_cache.items() if expires_at <= now
        ]
        for key in stale_keys:
            self._inspection_cache.pop(key, None)

    def snapshot(self) -> Dict[str, Any]:
        with self._inspection_lock:
            now = time.time()
            return {
                "inspection_cache_entries": len(self._inspection_cache),
                "inspection_cache_max_entries": self.INSPECTION_CACHE_MAX_ENTRIES,
                "inspection_cache_ttl_seconds": self.INSPECTION_CACHE_TTL_SECONDS,
                "stale_entries": sum(
                    1 for expires_at, _ in self._inspection_cache.values() if expires_at <= now
                ),
            }

    @staticmethod
    def _copy_inspection_result(result: Dict[str, Any]) -> Dict[str, Any]:
        copied = dict(result)
        if "resolution_path" in copied:
            copied["resolution_path"] = list(copied["resolution_path"])
        return copied

    def fetch_abi(
        self,
        web3: Web3,
        target_address: str,
        *,
        abi_fetcher: Callable[[str], Any],
    ) -> Dict[str, Any]:
        inspection = self.inspect_target(web3, target_address)
        actual_target = str(inspection["resolved_target"])
        self._cache.invalidate_stale()
        cached = self._cache.get(actual_target)
        if cached is not None:
            return {
                "target": actual_target,
                "abi": cached,
                "cache_hit": True,
                "proxy": dict(inspection),
            }
        abi = abi_fetcher(actual_target)
        self._cache.set(actual_target, abi)
        return {
            "target": actual_target,
            "abi": abi,
            "cache_hit": False,
            "proxy": dict(inspection),
        }

    @staticmethod
    def _read_slot_address(web3: Web3, address: str, slot: int) -> Optional[str]:
        raw = web3.eth.get_storage_at(cast(ChecksumAddress, address), slot)
        if not raw or raw == b"\x00" * 32:
            return None
        tail = raw[-20:]
        if tail == b"\x00" * 20:
            return None
        return Web3.to_checksum_address("0x" + tail.hex())

    @classmethod
    def _resolve_diamond_facet(cls, web3: Web3, target: str) -> Optional[str]:
        payload = cast(
            TxParams, {"to": target, "data": bytes.fromhex(DIAMOND_FACET_ADDRESS_SELECTOR[2:])}
        )
        try:
            raw = web3.eth.call(payload)
        except Exception:
            return None
        if not raw:
            return None
        if isinstance(raw, str):
            body = raw[2:] if raw.startswith("0x") else raw
            try:
                raw = bytes.fromhex(body)
            except ValueError:
                return None
        if not isinstance(raw, (bytes, bytearray)) or len(raw) < 32:
            return None
        decoded_address = ProxyPiercer._decode_abi_address(web3, bytes(raw)[:32])
        return decoded_address

    @staticmethod
    def _resolve_beacon_implementation(web3: Web3, beacon_address: str) -> Optional[str]:
        payload = cast(TxParams, {"to": beacon_address, "data": BEACON_IMPLEMENTATION_SELECTOR})
        raw = web3.eth.call(payload)
        if not raw:
            return None
        if isinstance(raw, str):
            body = raw[2:] if raw.startswith("0x") else raw
            try:
                raw = bytes.fromhex(body)
            except ValueError:
                return None
        if not isinstance(raw, (bytes, bytearray)) or len(raw) < 32:
            return None
        decoded_address = ProxyPiercer._decode_abi_address(web3, bytes(raw)[:32])
        if decoded_address is None:
            return None
        return decoded_address

    @staticmethod
    def _decode_abi_address(web3: Web3, raw: bytes) -> Optional[str]:
        try:
            if abi_decode is not None:
                decoded = abi_decode(["address"], raw)
            else:
                codec = getattr(web3, "codec", None) or Web3().codec
                decoded = codec.decode(["address"], raw)
        except Exception:
            return None
        address = decoded[0]
        if not isinstance(address, str) or not Web3.is_address(address):
            return None
        checksum = Web3.to_checksum_address(address)
        if int(checksum, 16) == 0:
            return None
        return checksum
