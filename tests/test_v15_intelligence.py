from __future__ import annotations

import tempfile
from typing import Any, Dict, Optional

import pytest
from lirix import Lirix
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.layers import AbiLRUCache, ProxyPiercer, ShadowAuditor, ShadowPolicySchema
from lirix.layers.l3_proxy_piercer import (
    EIP1822_PROXIABLE_SLOT,
    EIP1967_ADMIN_SLOT,
    EIP1967_BEACON_SLOT,
    EIP1967_IMPLEMENTATION_SLOT,
)
from web3 import Web3


def _slot_bytes(address: str) -> bytes:
    return bytes.fromhex("00" * 12 + Web3.to_checksum_address(address)[2:])


class _FakeEth:
    def __init__(
        self,
        *,
        storage: Optional[Dict[tuple[str, int], bytes]] = None,
        calls: Optional[Dict[tuple[str, str], bytes]] = None,
    ) -> None:
        self._storage = storage or {}
        self._calls = calls or {}

    def get_storage_at(self, address: str, slot: int) -> bytes:
        return self._storage.get((Web3.to_checksum_address(address), slot), b"\x00" * 32)

    def call(self, tx: Dict[str, Any]) -> bytes:
        to = Web3.to_checksum_address(str(tx["to"]))
        data = str(tx["data"]).lower()
        return self._calls.get((to, data), b"")


class _FakeWeb3:
    def __init__(
        self,
        *,
        storage: Optional[Dict[tuple[str, int], bytes]] = None,
        calls: Optional[Dict[tuple[str, str], bytes]] = None,
    ) -> None:
        self.eth = _FakeEth(storage=storage, calls=calls)


def test_l3_proxy_piercer_resolves_eip1967_implementation() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000001000")
    implementation = Web3.to_checksum_address("0x0000000000000000000000000000000000002000")
    web3 = _FakeWeb3(
        storage={(proxy, int(EIP1967_IMPLEMENTATION_SLOT, 16)): _slot_bytes(implementation)}
    )

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == implementation
    assert inspection["proxy_kind"] == "eip1967"


def test_l3_proxy_piercer_resolves_beacon_proxy() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000003000")
    beacon = Web3.to_checksum_address("0x0000000000000000000000000000000000004000")
    implementation = Web3.to_checksum_address("0x0000000000000000000000000000000000005000")
    web3 = _FakeWeb3(
        storage={(proxy, int(EIP1967_BEACON_SLOT, 16)): _slot_bytes(beacon)},
        calls={(beacon, "0x5c60da1b"): _slot_bytes(implementation).rjust(32, b"\x00")},
    )

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == implementation
    assert inspection["beacon"] == beacon
    assert inspection["proxy_kind"] == "beacon"


def test_l3_proxy_piercer_beacon_decode_rejects_short_payload() -> None:
    beacon = Web3.to_checksum_address("0x0000000000000000000000000000000000004000")
    web3 = _FakeWeb3(calls={(beacon, "0x5c60da1b"): b"\x00" * 12})

    resolved = ProxyPiercer._resolve_beacon_implementation(web3, beacon)  # type: ignore[arg-type]

    assert resolved is None


def test_l3_proxy_piercer_resolves_uups_slot() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000006000")
    implementation = Web3.to_checksum_address("0x0000000000000000000000000000000000007000")
    web3 = _FakeWeb3(
        storage={(proxy, int(EIP1822_PROXIABLE_SLOT, 16)): _slot_bytes(implementation)}
    )

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == implementation
    assert inspection["proxy_kind"] == "uups"


def test_l3_proxy_piercer_surfaces_admin_slot_for_fallback_verification() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000008000")
    admin = Web3.to_checksum_address("0x0000000000000000000000000000000000009000")
    web3 = _FakeWeb3(storage={(proxy, int(EIP1967_ADMIN_SLOT, 16)): _slot_bytes(admin)})

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == proxy
    assert inspection["admin"] == admin
    assert inspection["is_proxy"] is True
    assert inspection["proxy_kind"] == "admin_only_proxy"


def test_l3_abi_cache_hits_memory_without_refetch() -> None:
    clock = {"now": 1_000_000}
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp:
        cache = AbiLRUCache(
            sqlite_path=tmp.name,
            ttl_seconds=60,
            invalidation_interval_seconds=60,
            time_fn=lambda: clock["now"],
        )
        try:
            piercer = ProxyPiercer(abi_cache=cache)
            target = Web3.to_checksum_address("0x0000000000000000000000000000000000001010")
            web3 = _FakeWeb3()
            calls = {"count": 0}

            def fetcher(address: str) -> list[dict[str, str]]:
                calls["count"] += 1
                return [{"type": "function", "name": "foo", "target": address}]

            first = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)  # type: ignore[arg-type]
            second = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)  # type: ignore[arg-type]

            assert first["cache_hit"] is False
            assert second["cache_hit"] is True
            assert calls["count"] == 1
        finally:
            cache.close()


def test_l3_abi_cache_ttl_expiration_purges_and_refetches() -> None:
    clock = {"now": 2_000_000}
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as tmp:
        cache = AbiLRUCache(
            sqlite_path=tmp.name,
            ttl_seconds=5,
            invalidation_interval_seconds=1,
            time_fn=lambda: clock["now"],
        )
        try:
            piercer = ProxyPiercer(abi_cache=cache)
            target = Web3.to_checksum_address("0x0000000000000000000000000000000000002020")
            web3 = _FakeWeb3()
            calls = {"count": 0}

            def fetcher(address: str) -> list[dict[str, Any]]:
                calls["count"] += 1
                return [
                    {
                        "type": "function",
                        "name": "version",
                        "round": calls["count"],
                        "target": address,
                    }
                ]

            first = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)  # type: ignore[arg-type]
            clock["now"] += 10
            cache.invalidate_stale()
            second = piercer.fetch_abi(web3, target, abi_fetcher=fetcher)  # type: ignore[arg-type]

            assert first["cache_hit"] is False
            assert second["cache_hit"] is False
            assert calls["count"] == 2
            assert second["abi"][0]["round"] == 2
        finally:
            cache.close()


def test_l5_shadow_policy_rejects_forbidden_method_even_on_allowed_target() -> None:
    auditor = ShadowAuditor()
    target = Web3.to_checksum_address("0x0000000000000000000000000000000000003030")

    with pytest.raises(LirixPolicyViolationException) as exc_info:
        auditor.audit(
            payload={"to": target, "data": "0xa9059cbb00000000"},
            simulation_result={"simulation_ok": True, "slippage_bps": 10},
            security_policy=ShadowPolicySchema(
                allowed_target_contracts=[target],
                forbidden_methods=["0xa9059cbb"],
                max_slippage_bps=50,
            ),
        )

    assert exc_info.value.error_code == "LRX_SHADOW_POLICY_BLOCKED"
    assert exc_info.value.context["policy_key"] == "forbidden_methods"


def test_l5_shadow_policy_blocks_excessive_slippage_in_lirix_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "to": "0x0000000000000000000000000000000000004040",
        "data": "0x38ed173900000000",
    }
    guard = Lirix(rpc_urls=["https://example-rpc.invalid"])

    monkeypatch.setattr("lirix.IntentValidator.validate", lambda self, intent, draft: True)
    monkeypatch.setattr("lirix.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix.RPCManager.sync_reconcile", lambda self: 12345)
    monkeypatch.setattr("lirix.RPCManager.sync_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "layer": "L5",
            "simulation_ok": True,
            "metrics": {"slippage_bps": 250},
        },
    )

    with pytest.raises(LirixPolicyViolationException) as exc_info:
        guard.validate_and_simulate(
            "swap",
            payload,
            security_policy={
                "max_slippage_bps": 50,
                "allowed_target_contracts": "ANY",
                "forbidden_methods": [],
            },
        )

    assert exc_info.value.context["policy_key"] == "max_slippage_bps"
