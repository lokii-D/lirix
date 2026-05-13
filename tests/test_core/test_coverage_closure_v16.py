from __future__ import annotations

from typing import Mapping

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.evidence import QuorumVerdict, SecurityTrace, SimulationOutcome
from lirix.core.exceptions import RPCUnavailableException
from lirix.core.hook_contract import (
    HookContractRegistry,
    HookDecision,
    HookPatch,
    ReadonlyHookPayload,
    apply_hook_patch,
)
from lirix.core.hook_manager import HookManager

from tests.conftest import LOCAL_ANVIL_RPC_URL


def test_simulate_only_success_and_trace_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = Lirix(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=[LOCAL_ANVIL_RPC_URL],
        )
    )

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self: object) -> int:
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
            "simulation_assumptions": ["pinned_n_minus_1"],
            "policy_match_ids": ["p1"],
            "state_delta_digest": "deadbeef",
        },
    )

    async def _simulate_async(
        self: object,
        _payload: Mapping[str, object],
        *,
        async_web3: object,
        block_number: int,
        state_overrides: object | None = None,
    ) -> dict[str, object]:
        _ = async_web3, state_overrides
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
            "simulation_assumptions": ["pinned_n_minus_1"],
            "policy_match_ids": ["p1"],
            "state_delta_digest": "deadbeef",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)

    out = guard.simulate_only({"to": "0x1", "data": "0x"})
    assert out["agent_feedback"]["reason_code"] == "LIRIX_REASON_OK"
    assert out["security_trace"]["intent"] == "simulate_only"
    assert out["replay_bundle"]["bundle_digest"]
    assert "forensic_bundle" in out


def test_simulate_only_failure_attaches_agent_feedback_and_bundles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=[LOCAL_ANVIL_RPC_URL],
        )
    )

    def _boom(*args: object, **kwargs: object) -> int:
        raise RPCUnavailableException(
            human_readable_reason="rpc timeout",
            context={"layer": "L4", "reason": "timeout"},
        )

    async def _boom_async(*args: object, **kwargs: object) -> int:
        raise RPCUnavailableException(
            human_readable_reason="rpc timeout",
            context={"layer": "L4", "reason": "timeout"},
        )

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", _boom)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _boom_async)

    with pytest.raises(RPCUnavailableException) as exc_info:
        guard.simulate_only({"to": "0x1", "data": "0x"})

    ctx = exc_info.value.context
    assert ctx["agent_feedback"]["reason_code"] == "LIRIX_REASON_TIMEOUT"
    assert ctx["agent_feedback"]["retry_allowed"] is True
    assert ctx["replay_bundle"]["bundle_digest"]
    assert isinstance(ctx["forensic_bundle"]["reason_codes"], list)


def test_chain_adapter_resolve_l3_targets_is_covered() -> None:
    cfg = LirixConfig(chain_id=1, strict_mode=False, rpc_urls=[])
    guard = Lirix(cfg)
    targets = guard.chain_adapter.resolve_l3_targets()
    assert "multicall3_address" in targets
    assert "uniswap_v2_router" in targets
    assert guard.chain_adapter.profile.chain_id == 1


def test_evidence_optional_fields_and_session_id_branch() -> None:
    v = QuorumVerdict(
        block_number=1,
        selected_rpc_url=None,
        quorum_ok=True,
        required_votes=2,
        observed_votes=2,
        details={"x": 1},
    ).to_dict()
    assert v["required_votes"] == 2 and v["observed_votes"] == 2

    trace = SecurityTrace.new(
        correlation_id="c1",
        session_id="s1",
        intent="i",
        payload={"to": "0x1", "data": "0x"},
    ).to_dict()
    assert trace["session_id"] == "s1"

    trace2 = SecurityTrace.new(
        correlation_id="c2",
        intent="i",
        payload={"to": "0x1", "data": "0x"},
    ).to_dict()
    assert "session_id" not in trace2

    # state_delta digest branch: non-mapping should not derive digest
    so = SimulationOutcome(simulation_ok=True, layer="L5", details={"state_delta": []}).to_dict()
    assert "state_delta_digest" not in so


def test_hook_contract_registry_validation_and_patch_none_branch() -> None:
    reg = HookContractRegistry()
    reg.register("x", frozenset({"a", "b"}))
    state = reg.validate_payload("x", {"a": 1})
    assert state["valid"] is False and state["missing_fields"] == ["b"]

    # validate_result should accept controlled types
    assert reg.validate_result(HookDecision(status="approved")) is True
    assert reg.validate_result(object()) is False

    target = {"a": 1}
    assert apply_hook_patch(target, None) == {"a": 1}


def test_hook_manager_enforce_mode_hook_decision_fatal_is_rejected() -> None:
    mgr = HookManager(contract_mode="enforce")

    def reject(*args: object, **kwargs: object) -> HookDecision:
        return HookDecision(status="blocked", reason="no", failure_level="fatal")

    from lirix.core.constants import HOOK_PRE_VALIDATE

    mgr.register_hook(HOOK_PRE_VALIDATE, reject)
    out = mgr.invoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload={"a": 1})
    assert out[0]["ok"] is False
    assert out[0]["error_code"] == "LIRIX_HOOK_DECISION_REJECTED"


def test_hook_manager_applies_patch_in_threaded_and_async_isolated_paths() -> None:
    from lirix.core.constants import HOOK_PRE_VALIDATE

    mgr = HookManager(contract_mode="enforce")
    payload = {"a": 1}

    def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2})

    mgr.register_hook(HOOK_PRE_VALIDATE, patcher)
    mgr.invoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload=payload, timeout_sec=0.1)
    assert payload["b"] == 2

    amgr = HookManager(contract_mode="enforce")
    apayload = {"a": 1}
    amgr.register_hook(HOOK_PRE_VALIDATE, patcher)

    async def _run() -> None:
        await amgr.ainvoke_hooks_isolated(
            HOOK_PRE_VALIDATE, intent="swap", payload=apayload, timeout_sec=0.1
        )

    import asyncio

    asyncio.run(_run())
    assert apayload["b"] == 2


def test_hook_manager_wraps_payload_as_readonly_contract_view() -> None:
    from lirix.core.constants import HOOK_PRE_VALIDATE

    mgr = HookManager(contract_mode="enforce")
    seen: dict[str, object] = {}

    def inspector(*args: object, **kwargs: object) -> HookDecision:
        seen["payload"] = kwargs["payload"]
        return HookDecision(status="approved")

    mgr.register_hook(HOOK_PRE_VALIDATE, inspector)
    mgr.invoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload={"a": 1})
    assert isinstance(seen["payload"], ReadonlyHookPayload)


def test_hook_manager_payload_wrap_false_branch_when_payload_not_dict() -> None:
    from lirix.core.constants import HOOK_PRE_VALIDATE

    mgr = HookManager(contract_mode="enforce")
    seen: dict[str, object] = {}

    def inspector(*args: object, **kwargs: object) -> HookDecision:
        seen["payload"] = kwargs["payload"]
        return HookDecision(status="approved")

    mgr.register_hook(HOOK_PRE_VALIDATE, inspector)
    mgr.invoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload="x")
    assert seen["payload"] == "x"
