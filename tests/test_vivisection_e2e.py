from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Any

import pytest
from lirix.cli import scaffold_init
from lirix.integrations.langchain.tool import LirixSecurityValidator
from lirix.layers import ProxyPiercer
from lirix.layers.l3_proxy_piercer import EIP1967_IMPLEMENTATION_SLOT
from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_sandbox_simulator import SandboxSimulator
from web3 import Web3


def _slot_bytes(address: str) -> bytes:
    return bytes.fromhex("00" * 12 + Web3.to_checksum_address(address)[2:])


class _FakeEth:
    def __init__(self, implementation: str) -> None:
        self._implementation = Web3.to_checksum_address(implementation)

    def get_storage_at(self, address: str, slot: int) -> bytes:
        if slot == int(EIP1967_IMPLEMENTATION_SLOT, 16):
            return _slot_bytes(self._implementation)
        return b"\x00" * 32


class _FakeWeb3:
    def __init__(self, implementation: str) -> None:
        self.eth = _FakeEth(implementation)


class _FakeAsyncEth:
    async def call(
        self, tx: Any, block_identifier: Any = None, state_override: Any = None
    ) -> bytes:
        return b"vivisection"


class _FakeAsyncWeb3:
    def __init__(self) -> None:
        self.eth = _FakeAsyncEth()


@pytest.mark.asyncio  # type: ignore[misc]
@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.slow
async def test_v15_vivisection_e2e(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scaffold_init(tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        policy_module = importlib.import_module("lirix_policy")
        default_strict_policy = policy_module.DEFAULT_STRICT_POLICY
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("lirix_policy", None)

    proxy_address = Web3.to_checksum_address("0x0000000000000000000000000000000000001000")
    implementation_address = Web3.to_checksum_address("0x0000000000000000000000000000000000002000")
    attack_payload = (
        f'{{"intent":"swap","to":"{proxy_address}","data":"0x38ed173900000000",'
        '"expected_return":0}'
    )
    events: list[str] = []
    l4_state: dict[str, Any] = {}

    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate",
        lambda self, intent, draft: True,
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)

    def fake_l3_validate(self: Any, payload: dict[str, Any]) -> bool:
        inspection = ProxyPiercer().inspect_target(_FakeWeb3(implementation_address), proxy_address)  # type: ignore[arg-type]
        payload["to"] = str(inspection["resolved_target"])
        payload["data"] = "0x38ed173900000000"
        payload["expected_return"] = 0
        payload["_l3_proxy_inspection"] = inspection
        events.append("L3")
        return True

    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", fake_l3_validate)

    async def fake_async_reconcile(self: RPCManager) -> int:
        async def one_node(node: str) -> dict[str, Any]:
            await asyncio.sleep(0)
            return {"node": node, "slippage_bps": 10_000, "loss_pct": 100}

        deltas = await asyncio.gather(one_node("rpc-a"), one_node("rpc-b"), one_node("rpc-c"))
        l4_state["deltas"] = deltas
        events.append("L4")
        return 18_765_432

    monkeypatch.setattr(RPCManager, "async_reconcile", fake_async_reconcile)
    monkeypatch.setattr(RPCManager, "async_web3", lambda self: _FakeAsyncWeb3())

    async def fake_simulate_async(
        self: SandboxSimulator,
        payload: Any,
        *,
        async_web3: Any,
        block_number: int,
        state_overrides: Any = None,
    ) -> dict[str, Any]:
        deltas = l4_state["deltas"]
        assert len(deltas) == 3
        assert all(delta["loss_pct"] == 100 for delta in deltas)
        await async_web3.eth.call(
            {"to": payload["to"], "data": payload["data"]}, block_identifier=block_number
        )
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "proxy_inspection": payload["_l3_proxy_inspection"],
            "metrics": {
                "slippage_bps": max(delta["slippage_bps"] for delta in deltas),
                "loss_pct": max(delta["loss_pct"] for delta in deltas),
            },
            "agent_assertion": {"expected_return": payload["expected_return"]},
        }

    monkeypatch.setattr(SandboxSimulator, "simulate_async", fake_simulate_async)
    monkeypatch.setattr(
        "lirix.Lirix.validate_and_simulate",
        lambda self, intent, payload, **kwargs: asyncio.run(
            self.async_validate_and_simulate(intent, payload, **kwargs)
        ),
    )

    validator = LirixSecurityValidator(
        rpc_urls=["https://rpc-a.invalid", "https://rpc-b.invalid", "https://rpc-c.invalid"],
        default_intent="swap",
        policy=default_strict_policy,
    )

    result = await validator._arun(
        attack_payload,
        intent="swap",
        state_delta_assertions={"expected_return": 0},
    )

    assert events == ["L3", "L4"]
    assert isinstance(result, str)
    assert "Transaction Blocked by Lirix Policy:" in result
    assert "max_slippage_bps violated" in result
    assert "observed=10000" in result
