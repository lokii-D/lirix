from __future__ import annotations

import errno
import threading
from typing import Any

import lirix.layers.l3_proxy_piercer as piercer_mod
import pytest
from lirix.core.exceptions import LirixSecurityException
from lirix.layers.l3_proxy_piercer import AbiLRUCache, ProxyPiercer
from web3 import Web3
from web3.exceptions import ContractLogicError, Web3Exception


class _Eth:
    def __init__(self, *, call_result: Any = b"", call_error: Exception | None = None) -> None:
        self._call_result = call_result
        self._call_error = call_error

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return b"\x00" * 32

    def call(self, payload: dict[str, Any]) -> Any:
        if self._call_error is not None:
            raise self._call_error
        return self._call_result


class _W3:
    def __init__(self, eth: _Eth) -> None:
        self.eth = eth


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent(tmp_path) -> None:
    now = 100
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi.sqlite3"),
        ttl_seconds=5,
        invalidation_interval_seconds=60,
        time_fn=lambda: now,
    )
    address = "0x00000000000000000000000000000000000000A1"
    cache.set(address, [{"v": 1}])
    cache.set(address, [{"v": 2}])  # existing-key update branch
    cache._memory.clear()  # force DB stale path
    now = 200
    assert cache.get(address) is None
    cache.close()
    cache.close()  # idempotent close branch


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent_2(tmp_path) -> None:
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi.sqlite3"),
        max_entries=1,
        ttl_seconds=60,
        invalidation_interval_seconds=1,
    )
    cache.set("0x00000000000000000000000000000000000000B1", [{"n": 1}])
    cache.set("0x00000000000000000000000000000000000000B2", [{"n": 2}])  # trim branch
    cache.invalidate("0x00000000000000000000000000000000000000B2")
    assert cache.get("0x00000000000000000000000000000000000000B2") is None

    cache._closed = True
    cache._stop_event = threading.Event()
    cache._stop_event.set()
    cache._invalidation_loop()  # covers while-exit and closed-guard branches
    cache._closed = False
    cache.close()


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    piercer = ProxyPiercer()
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000C1")
    result = {
        "target": target,
        "resolved_target": target,
        "proxy_kind": "direct",
        "implementation": None,
        "beacon": None,
        "beacon_implementation": None,
        "admin": None,
        "uups_implementation": None,
        "is_proxy": False,
        "resolution_path": [],
    }
    monkeypatch.setattr(
        ProxyPiercer, "_read_slot_address", staticmethod(lambda *args, **kwargs: None)
    )
    monkeypatch.setattr(piercer, "_resolve_diamond_facet", lambda w3, t: None)

    now = [100.0]
    monkeypatch.setattr(piercer_mod.time, "monotonic", lambda: now[0])
    piercer.INSPECTION_CACHE_TTL_SECONDS = 1
    piercer._store_inspection_cache(target, result, now[0])
    now[0] = 200.0
    inspected = piercer.inspect_target(_W3(_Eth()), target)
    assert inspected["proxy_kind"] == "direct"  # expired cached entry was removed and recomputed

    piercer.INSPECTION_CACHE_MAX_ENTRIES = 1
    piercer._store_inspection_cache(
        Web3.to_checksum_address("0x00000000000000000000000000000000000000C2"),
        result,
        now[0],
    )
    piercer._store_inspection_cache(
        Web3.to_checksum_address("0x00000000000000000000000000000000000000C3"),
        result,
        now[0],
    )
    assert len(piercer._inspection_cache) == 1

    piercer._inspection_cache[target] = (now[0] - 1, result)
    piercer._purge_stale_inspection_cache_locked(now[0])
    assert target not in piercer._inspection_cache


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent_4() -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000D1")
    beacon = Web3.to_checksum_address("0x00000000000000000000000000000000000000D2")
    implementation = Web3.to_checksum_address("0x00000000000000000000000000000000000000D3")

    class _Slots:
        def __init__(self, values: list[str | None]) -> None:
            self._i = 0
            self._values = values

        def __call__(self, web3: Any, address: str, slot: int) -> str | None:
            value = self._values[self._i]
            self._i += 1
            return value

    slot_reader = _Slots([None, implementation, beacon, None])
    piercer = ProxyPiercer()
    original = ProxyPiercer._read_slot_address
    ProxyPiercer._read_slot_address = staticmethod(slot_reader)  # type: ignore[method-assign]
    try:
        with pytest.MonkeyPatch.context() as m:
            m.setattr(piercer, "_resolve_beacon_implementation", lambda w3, b: None)
            m.setattr(piercer, "_resolve_diamond_facet", lambda w3, t: None)
            out = piercer.inspect_target(_W3(_Eth()), target)
            assert out["proxy_kind"] == "beacon_unresolved"
            assert "fallback.eip1967_implementation" in out["resolution_path"]

        slot_reader = _Slots([None, None, beacon, None])
        ProxyPiercer._read_slot_address = staticmethod(slot_reader)  # type: ignore[method-assign]
        piercer2 = ProxyPiercer()
        with pytest.MonkeyPatch.context() as m:
            m.setattr(piercer2, "_resolve_beacon_implementation", lambda w3, b: None)
            m.setattr(piercer2, "_resolve_diamond_facet", lambda w3, t: None)
            out2 = piercer2.inspect_target(_W3(_Eth()), target)
            assert out2["resolved_target"] == target
            assert "fallback.self" in out2["resolution_path"]
    finally:
        ProxyPiercer._read_slot_address = staticmethod(original)  # type: ignore[method-assign]


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = Web3.to_checksum_address("0x00000000000000000000000000000000000000E1")

    class _ZeroTailEth:
        def get_storage_at(self, address: str, slot: int) -> bytes:
            return b"\x11" * 12 + b"\x00" * 20

        def call(self, payload: dict[str, Any]) -> Any:
            return b""

    assert ProxyPiercer._read_slot_address(_W3(_ZeroTailEth()), target, 1) is None
    piercer = ProxyPiercer()
    with pytest.raises(LirixSecurityException) as boom_exc:
        piercer._resolve_diamond_facet(_W3(_Eth(call_error=RuntimeError("boom"))), target)
    assert boom_exc.value.context.get("reason") == "diamond_facet_unexpected"
    assert "boom" in str(boom_exc.value.context.get("detail", ""))
    assert piercer._resolve_diamond_facet(_W3(_Eth(call_result="zzzz")), target) is None
    assert piercer._resolve_diamond_facet(_W3(_Eth(call_result=object())), target) is None
    assert piercer._resolve_beacon_implementation(_W3(_Eth(call_result="zzzz")), target) is None

    monkeypatch.setattr(piercer, "_decode_abi_address", lambda w3, raw: None)
    raw = "0x" + ("00" * 32)
    assert piercer._resolve_beacon_implementation(_W3(_Eth(call_result=raw)), target) is None


def test_abi_lru_cache_context_manager_exit_closes(tmp_path) -> None:
    db = tmp_path / "ctx.sqlite3"
    cache_ref: dict[str, AbiLRUCache] = {}
    with AbiLRUCache(
        sqlite_path=str(db),
        ttl_seconds=30,
        invalidation_interval_seconds=3600,
    ) as cache:
        cache_ref["c"] = cache
        cache.set("0x0000000000000000000000000000000000000F01", [{"k": 1}])
    assert cache_ref["c"]._closed is True


def test_proxy_piercer_diamond_beacon_transport_and_decode_exception_paths() -> None:
    target = Web3.to_checksum_address("0x0000000000000000000000000000000000000e20")
    beacon = Web3.to_checksum_address("0x0000000000000000000000000000000000000e30")
    piercer = ProxyPiercer()

    class _ContractRevertEth:
        def get_storage_at(self, address: str, slot: int) -> bytes:
            return b"\x00" * 32

        def call(self, payload: dict[str, Any]) -> Any:
            raise ContractLogicError("reverted")

    assert piercer._resolve_diamond_facet(_W3(_ContractRevertEth()), target) is None

    class _DiamondWeb3Exc:
        def get_storage_at(self, address: str, slot: int) -> bytes:
            return b"\x00" * 32

        def call(self, payload: dict[str, Any]) -> Any:
            raise Web3Exception("transport")

    with pytest.raises(LirixSecurityException) as d_w3:
        piercer._resolve_diamond_facet(_W3(_DiamondWeb3Exc()), target)
    assert d_w3.value.context.get("reason") == "diamond_facet_eth_call"

    class _DiamondTimeout:
        def get_storage_at(self, address: str, slot: int) -> bytes:
            return b"\x00" * 32

        def call(self, payload: dict[str, Any]) -> Any:
            raise TimeoutError()

    with pytest.raises(LirixSecurityException) as d_to:
        piercer._resolve_diamond_facet(_W3(_DiamondTimeout()), target)
    assert d_to.value.context.get("reason") == "diamond_facet_transport"

    class _BeaconContractLogic:
        def call(self, payload: dict[str, Any]) -> Any:
            raise ContractLogicError("beacon revert")

    assert piercer._resolve_beacon_implementation(_W3(_BeaconContractLogic()), beacon) is None

    class _BeaconWeb3Exc:
        def call(self, payload: dict[str, Any]) -> Any:
            raise Web3Exception("beacon transport")

    with pytest.raises(LirixSecurityException) as b_w3:
        piercer._resolve_beacon_implementation(_W3(_BeaconWeb3Exc()), beacon)
    assert b_w3.value.context.get("reason") == "beacon_implementation_eth_call"

    class _BeaconOSError:
        def call(self, payload: dict[str, Any]) -> Any:
            raise OSError(errno.ETIMEDOUT, "timed out")

    with pytest.raises(LirixSecurityException) as b_os:
        piercer._resolve_beacon_implementation(_W3(_BeaconOSError()), beacon)
    assert b_os.value.context.get("reason") == "beacon_implementation_transport"

    class _BeaconUnexpected:
        def call(self, payload: dict[str, Any]) -> Any:
            raise RuntimeError("unexpected")

    with pytest.raises(LirixSecurityException) as b_un:
        piercer._resolve_beacon_implementation(_W3(_BeaconUnexpected()), beacon)
    assert b_un.value.context.get("reason") == "beacon_implementation_unexpected"


def test_proxy_piercer_decode_abi_address_surfaces_web3_and_unexpected_errors() -> None:
    original = piercer_mod.abi_decode
    piercer = ProxyPiercer()
    try:
        piercer_mod.abi_decode = None

        class _CodecWeb3Exc:
            def decode(self, _types: object, _raw: object) -> None:
                raise Web3Exception("codec boom")

        class _W3CodecA:
            codec = _CodecWeb3Exc()

        with pytest.raises(LirixSecurityException) as ei:
            piercer._decode_abi_address(_W3CodecA(), b"\x22" * 32)
        assert ei.value.context.get("reason") == "proxy_address_abi_decode"

        class _CodecUnexpected:
            def decode(self, _types: object, _raw: object) -> None:
                raise RuntimeError("codec surprise")

        class _W3CodecB:
            codec = _CodecUnexpected()

        with pytest.raises(LirixSecurityException) as ei2:
            piercer._decode_abi_address(_W3CodecB(), b"\x22" * 32)
        assert ei2.value.context.get("reason") == "proxy_address_decode_unexpected"
    finally:
        piercer_mod.abi_decode = original


def test_test_proxy_piercer_abi_cache_db_stale_set_update_close_idempotent_6() -> None:
    original = piercer_mod.abi_decode
    try:
        piercer_mod.abi_decode = None

        class _Codec:
            def decode(self, _types, _raw):
                raise ValueError("decode failed")

        class _CodecW3:
            codec = _Codec()

        assert ProxyPiercer()._decode_abi_address(_CodecW3(), b"\x00" * 32) is None

        class _Codec2:
            def decode(self, _types, _raw):
                return ("invalid-address",)

        class _CodecW32:
            codec = _Codec2()

        assert ProxyPiercer()._decode_abi_address(_CodecW32(), b"\x00" * 32) is None
    finally:
        piercer_mod.abi_decode = original
