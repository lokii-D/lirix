from __future__ import annotations

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
from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_sandbox_simulator import SandboxSimulator
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


def test_proxy_piercer_resolves_eip1967_implementation_slot() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000001000")
    implementation = Web3.to_checksum_address("0x0000000000000000000000000000000000002000")
    web3 = _FakeWeb3(
        storage={(proxy, int(EIP1967_IMPLEMENTATION_SLOT, 16)): _slot_bytes(implementation)}
    )

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == implementation
    assert inspection["proxy_kind"] == "eip1967"


def test_proxy_piercer_resolves_beacon_implementation_via_call() -> None:
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


def test_beacon_resolution_returns_none_for_short_payload() -> None:
    beacon = Web3.to_checksum_address("0x0000000000000000000000000000000000004000")
    web3 = _FakeWeb3(calls={(beacon, "0x5c60da1b"): b"\x00" * 12})

    resolved = ProxyPiercer()._resolve_beacon_implementation(web3, beacon)  # type: ignore[arg-type]

    assert resolved is None


def test_proxy_piercer_resolves_uups_implementation_slot() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000006000")
    implementation = Web3.to_checksum_address("0x0000000000000000000000000000000000007000")
    web3 = _FakeWeb3(
        storage={(proxy, int(EIP1822_PROXIABLE_SLOT, 16)): _slot_bytes(implementation)}
    )

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == implementation
    assert inspection["proxy_kind"] == "uups"


def test_proxy_piercer_marks_admin_only_proxy_without_implementation() -> None:
    proxy = Web3.to_checksum_address("0x0000000000000000000000000000000000008000")
    admin = Web3.to_checksum_address("0x0000000000000000000000000000000000009000")
    web3 = _FakeWeb3(storage={(proxy, int(EIP1967_ADMIN_SLOT, 16)): _slot_bytes(admin)})

    inspection = ProxyPiercer().inspect_target(web3, proxy)  # type: ignore[arg-type]

    assert inspection["resolved_target"] == proxy
    assert inspection["admin"] == admin
    assert inspection["is_proxy"] is True
    assert inspection["proxy_kind"] == "admin_only_proxy"


def test_abi_cache_returns_hit_on_repeated_fetch(tmp_path: Any) -> None:
    clock = {"now": 1_000_000}
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi-cache-hits.sqlite3"),
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


def test_abi_cache_ttl_expiration_triggers_refetch(tmp_path: Any) -> None:
    clock = {"now": 2_000_000}
    cache = AbiLRUCache(
        sqlite_path=str(tmp_path / "abi-cache-ttl.sqlite3"),
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


def test_shadow_auditor_blocks_forbidden_method_even_when_simulation_ok() -> None:
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


def test_lirix_validate_and_simulate_enforces_slippage_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "to": "0x0000000000000000000000000000000000004040",
        "data": "0x38ed173900000000",
    }
    guard = Lirix(rpc_urls=["https://example-rpc.invalid"])

    monkeypatch.setattr(
        "lirix.layers.l1_intent_validator.IntentValidator.validate",
        lambda self, intent, draft: True,
    )
    monkeypatch.setattr(
        "lirix.layers.l2_schema_validator.SchemaValidator.validate", lambda self, draft: True
    )
    monkeypatch.setattr(
        "lirix.layers.l3_defi_parser.DeFiPayloadParser.validate", lambda self, draft: True
    )

    async def _fake_async_reconcile(self: RPCManager) -> int:
        return 12345

    def _fake_async_web3(self: RPCManager) -> object:
        return object()

    monkeypatch.setattr(RPCManager, "async_reconcile", _fake_async_reconcile)
    monkeypatch.setattr(RPCManager, "async_web3", _fake_async_web3)

    async def _fake_simulate_async(
        self: SandboxSimulator,
        draft: object,
        *,
        async_web3: object,
        block_number: int,
        state_overrides: object = None,
    ) -> dict[str, object]:
        _ = (draft, async_web3, block_number, state_overrides)
        return {"layer": "L5", "simulation_ok": True, "metrics": {"slippage_bps": 250}}

    monkeypatch.setattr(SandboxSimulator, "simulate_async", _fake_simulate_async)

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
    assert "security_trace" in exc_info.value.context
    trace = exc_info.value.context["security_trace"]
    assert trace["correlation_id"]
    assert trace.get("session_id")
    assert any(step["status"] == "rejected" for step in trace["steps"])


def test_lirix_validate_and_simulate_returns_decoupled_outcomes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "to": "0x0000000000000000000000000000000000004040",
        "data": "0x38ed173900000000",
    }
    guard = Lirix(rpc_urls=["https://example-rpc.invalid"])

    monkeypatch.setattr(
        "lirix.layers.l1_intent_validator.IntentValidator.validate",
        lambda self, intent, draft: True,
    )
    monkeypatch.setattr(
        "lirix.layers.l2_schema_validator.SchemaValidator.validate", lambda self, draft: True
    )
    monkeypatch.setattr(
        "lirix.layers.l3_defi_parser.DeFiPayloadParser.validate", lambda self, draft: True
    )

    async def _fake_async_reconcile(self: RPCManager) -> int:
        return 12345

    def _fake_async_web3(self: RPCManager) -> object:
        return object()

    monkeypatch.setattr(RPCManager, "async_reconcile", _fake_async_reconcile)
    monkeypatch.setattr(RPCManager, "async_web3", _fake_async_web3)

    async def _fake_simulate_async(
        self: SandboxSimulator,
        draft: object,
        *,
        async_web3: object,
        block_number: int,
        state_overrides: object = None,
    ) -> dict[str, object]:
        _ = (draft, async_web3, block_number, state_overrides)
        return {"layer": "L5", "simulation_ok": True, "metrics": {"slippage_bps": 10}}

    monkeypatch.setattr(SandboxSimulator, "simulate_async", _fake_simulate_async)

    out = guard.validate_and_simulate(
        "swap",
        payload,
        security_policy={
            "max_slippage_bps": 50,
            "allowed_target_contracts": "ANY",
            "forbidden_methods": [],
        },
    )

    assert out["validated"] is True
    assert out["simulation_outcome"]["simulation_ok"] is True
    assert out["policy_decision"]["policy_id"] == "lirix-default"
    assert out["security_trace"]["correlation_id"]
    assert out["security_trace"].get("session_id")
    assert out["validation_session"]["session_id"] == out["security_trace"]["session_id"]
    assert any(step["layer"] == "L4" for step in out["security_trace"]["steps"])
