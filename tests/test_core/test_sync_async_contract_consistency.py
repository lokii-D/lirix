from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix import Lirix
from lirix.core import HookExecutionException
from lirix.core.config import LirixConfig
from lirix.core.constants import (
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
)
from lirix.core.exceptions import (
    ConfigurationGuardException,
    InvalidIntentException,
    LirixPolicyViolationException,
    MaliciousPayloadException,
    RPCUnavailableException,
    SchemaValidationException,
    SimulationFailedException,
)
from lirix.core.session import ValidationSession


def _mapping_keys_equal(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert set(a.keys()) == set(b.keys())


def _assert_replay_bundle_deterministic_value_parity(a: dict[str, Any], b: dict[str, Any]) -> None:
    """Compare replay fields that must not diverge between sync/async for the same config path."""
    assert a["bundle_version"] == b["bundle_version"]
    assert a["config_fingerprint"] == b["config_fingerprint"]
    assert a["migration_modes"] == b["migration_modes"]
    assert a.get("registry_closure_digest") == b.get("registry_closure_digest")
    assert a["replay_proof"] == b["replay_proof"]
    assert a["artifact_digests"] == b["artifact_digests"]


def _replay_bundle_stable_keys(rb: dict[str, Any]) -> None:
    expected = {
        "bundle_version",
        "bundle_digest",
        "migration_modes",
        "config_fingerprint",
        "last_trace_digest",
        "artifact_digests",
        "replay_proof",
        "timeline_size",
        "decision_count",
        "payload",
    }
    assert expected <= set(rb.keys())
    payload = rb.get("payload")
    assert isinstance(payload, dict)
    assert {"session_id", "timeline", "state", "correlation_ids", "created_at"} <= set(
        payload.keys()
    )


def _assert_enriched_failure_context_parity(
    sync_exc: BaseException, async_exc: BaseException
) -> None:
    sctx = getattr(sync_exc, "context", None)
    actx = getattr(async_exc, "context", None)
    assert isinstance(sctx, dict) and isinstance(actx, dict)
    s_fp = sctx.get("failure_protocol")
    a_fp = actx.get("failure_protocol")
    if isinstance(s_fp, dict) and isinstance(a_fp, dict):
        assert set(s_fp.keys()) == set(a_fp.keys())
        sync_proj = Lirix.resolve_failure_protocol(sctx)
        async_proj = Lirix.resolve_failure_protocol(actx)
        assert set(sync_proj.keys()) == set(async_proj.keys())
    else:
        assert s_fp is None and a_fp is None
    s_af = sctx.get("agent_feedback")
    a_af = actx.get("agent_feedback")
    if isinstance(s_af, dict) and isinstance(a_af, dict):
        assert s_af.get("reason_code") == a_af.get("reason_code")
    s_rb = sctx.get("replay_bundle")
    a_rb = actx.get("replay_bundle")
    if isinstance(s_rb, dict) and isinstance(a_rb, dict):
        assert set(s_rb.keys()) == set(a_rb.keys())
        _replay_bundle_stable_keys(s_rb)
        _replay_bundle_stable_keys(a_rb)


def _evidence_v2_layer_keys(ev: dict[str, Any]) -> None:
    for layer_key in ("l1", "l2", "l3", "l4", "l5", "policy"):
        layer = ev.get(layer_key)
        if not isinstance(layer, dict):
            continue
        assert {"schema_version", "layer", "status", "details"} <= set(layer.keys())


def _install_success_monkeypatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        },
    )

    async def _simulate_async(self, payload, async_web3, block_number, state_overrides=None):  # type: ignore[no-untyped-def]
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)


def test_validate_and_simulate_sync_async_success_contract_consistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])

    sync_out = guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})
    async_out = asyncio.run(guard.async_validate_and_simulate("swap", {"to": "0x1", "data": "0x"}))

    assert sync_out["status"] == async_out["status"] == "approved"
    assert sync_out["decision"] == async_out["decision"] == "approved"
    assert set(sync_out.keys()) == set(async_out.keys())
    assert set(sync_out["payload"].keys()) == set(async_out["payload"].keys())
    assert sync_out["payload"]["simulation_ok"] is True
    assert async_out["payload"]["simulation_ok"] is True
    assert sync_out["evidence_schema_version"] == async_out["evidence_schema_version"]
    _assert_replay_bundle_deterministic_value_parity(
        sync_out["replay_bundle"], async_out["replay_bundle"]
    )


def test_validate_and_simulate_sync_async_delegate_to_single_source_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake_runner(self: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(str(kwargs["kind"]))
        return {"runner_kind": kwargs["kind"]}

    monkeypatch.setattr(
        "lirix.core.orchestrator.LirixPipelineOrchestrator.run_full",
        _fake_runner,
    )
    guard = Lirix(rpc_urls=["https://example.invalid"])

    sync_out = guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})
    async_out = asyncio.run(guard.async_validate_and_simulate("swap", {"to": "0x1", "data": "0x"}))

    assert sync_out["runner_kind"] == "validate_and_simulate"
    assert async_out["runner_kind"] == "async_validate_and_simulate"
    assert calls == ["validate_and_simulate", "async_validate_and_simulate"]


@pytest.mark.parametrize(
    "hook_point",
    [
        HOOK_PRE_VALIDATE,
        HOOK_PRE_SIMULATION,
        HOOK_POST_SIMULATION,
        HOOK_POST_VALIDATE,
    ],
)
def test_validate_and_simulate_blocking_hooks_sync_async_failure_mapping_consistent(
    monkeypatch: pytest.MonkeyPatch,
    hook_point: str,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _blocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    async def _ablocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.invoke_hooks_isolated", _blocked)
    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ablocked)
    guard = Lirix(rpc_urls=["https://example.invalid"])

    with pytest.raises(HookExecutionException) as sync_err:
        guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})
    with pytest.raises(HookExecutionException) as async_err:
        asyncio.run(guard.async_validate_and_simulate("swap", {"to": "0x1", "data": "0x"}))

    sync_ctx = sync_err.value.context
    async_ctx = async_err.value.context
    assert sync_ctx["layer"] == async_ctx["layer"] == "hooks"
    assert sync_ctx["reason"] == async_ctx["reason"] == "hook_blocked"


@pytest.mark.parametrize("hook_point", [HOOK_PRE_VALIDATE, HOOK_POST_VALIDATE])
def test_validate_only_blocking_hooks_sync_async_failure_mapping_consistent(
    monkeypatch: pytest.MonkeyPatch,
    hook_point: str,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _blocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    async def _ablocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.invoke_hooks_isolated", _blocked)
    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ablocked)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = {"to": "0x1", "data": "0x"}

    with pytest.raises(HookExecutionException) as sync_err:
        guard.validate_only("swap", payload)
    with pytest.raises(HookExecutionException) as async_err:
        asyncio.run(guard.async_validate_only("swap", payload))

    sync_ctx = sync_err.value.context
    async_ctx = async_err.value.context
    assert sync_ctx["layer"] == async_ctx["layer"] == "hooks"
    assert sync_ctx["reason"] == async_ctx["reason"] == "hook_blocked"


@pytest.mark.parametrize("hook_point", [HOOK_PRE_SIMULATION, HOOK_POST_SIMULATION])
def test_simulate_only_blocking_hooks_after_prior_validate_sync_async_consistent(
    monkeypatch: pytest.MonkeyPatch,
    hook_point: str,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _blocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    async def _ablocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.invoke_hooks_isolated", _blocked)
    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ablocked)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    sess = ValidationSession()
    guard.validate_only("swap", payload, session=sess)

    with pytest.raises(HookExecutionException) as sync_err:
        guard.simulate_only(payload, session=sess)
    with pytest.raises(HookExecutionException) as async_err:
        asyncio.run(guard.async_simulate_only(payload, session=sess))

    sync_ctx = sync_err.value.context
    async_ctx = async_err.value.context
    assert sync_ctx["layer"] == async_ctx["layer"] == "hooks"
    assert sync_ctx["reason"] == async_ctx["reason"] == "hook_blocked"


def test_validate_only_sync_async_success_contract_consistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = {"to": "0x1", "data": "0x"}

    sync_out = guard.validate_only("swap", payload)
    async_out = asyncio.run(guard.async_validate_only("swap", payload))

    _mapping_keys_equal(sync_out, async_out)
    _mapping_keys_equal(sync_out["payload"], async_out["payload"])
    _mapping_keys_equal(sync_out["agent_feedback"], async_out["agent_feedback"])
    _replay_bundle_stable_keys(sync_out["replay_bundle"])
    _replay_bundle_stable_keys(async_out["replay_bundle"])
    _mapping_keys_equal(sync_out["replay_bundle"], async_out["replay_bundle"])
    assert sync_out["evidence_schema_version"] == async_out["evidence_schema_version"]
    _assert_replay_bundle_deterministic_value_parity(
        sync_out["replay_bundle"], async_out["replay_bundle"]
    )
    assert set(sync_out["evidence_v2"].keys()) == set(async_out["evidence_v2"].keys())
    _evidence_v2_layer_keys(sync_out["evidence_v2"])
    _evidence_v2_layer_keys(async_out["evidence_v2"])


def test_simulate_only_sync_async_success_contract_consistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    payload = {"to": "0x1", "data": "0x"}

    sync_out = guard.simulate_only(payload)
    async_out = asyncio.run(guard.async_simulate_only(payload))

    _mapping_keys_equal(sync_out, async_out)
    _mapping_keys_equal(sync_out["payload"], async_out["payload"])
    _mapping_keys_equal(sync_out["agent_feedback"], async_out["agent_feedback"])
    _replay_bundle_stable_keys(sync_out["replay_bundle"])
    _replay_bundle_stable_keys(async_out["replay_bundle"])
    _mapping_keys_equal(sync_out["replay_bundle"], async_out["replay_bundle"])
    assert sync_out["evidence_schema_version"] == async_out["evidence_schema_version"]
    _assert_replay_bundle_deterministic_value_parity(
        sync_out["replay_bundle"], async_out["replay_bundle"]
    )
    assert set(sync_out["evidence_v2"].keys()) == set(async_out["evidence_v2"].keys())
    _evidence_v2_layer_keys(sync_out["evidence_v2"])
    _evidence_v2_layer_keys(async_out["evidence_v2"])


@pytest.mark.parametrize(
    "hook_point",
    [
        HOOK_PRE_VALIDATE,
        HOOK_PRE_SIMULATION,
        HOOK_POST_SIMULATION,
        HOOK_POST_VALIDATE,
    ],
)
def test_validate_and_simulate_blocking_hooks_sync_async_failure_protocol_field_parity(
    monkeypatch: pytest.MonkeyPatch,
    hook_point: str,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _blocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    async def _ablocked(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        if hp == hook_point:
            return [{"ok": False, "failure_level": "fatal", "reason": "contract_test_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.invoke_hooks_isolated", _blocked)
    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ablocked)
    guard = Lirix(rpc_urls=["https://example.invalid"])

    with pytest.raises(HookExecutionException) as sync_err:
        guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})
    with pytest.raises(HookExecutionException) as async_err:
        asyncio.run(guard.async_validate_and_simulate("swap", {"to": "0x1", "data": "0x"}))

    sync_ctx = sync_err.value.context
    async_ctx = async_err.value.context
    assert isinstance(sync_ctx, dict) and isinstance(async_ctx, dict)
    sync_fp = sync_ctx.get("failure_protocol")
    async_fp = async_ctx.get("failure_protocol")
    assert isinstance(sync_fp, dict) and isinstance(async_fp, dict)
    assert set(sync_fp.keys()) == set(async_fp.keys())

    sync_proj = Lirix.resolve_failure_protocol(sync_ctx)
    async_proj = Lirix.resolve_failure_protocol(async_ctx)
    assert set(sync_proj.keys()) == set(async_proj.keys())


def _valid_l1_payload() -> dict[str, Any]:
    return {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }


def _simulate_gate_config() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=["https://example.invalid"],
        simulate_only_requires_prior_validate=True,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


@pytest.mark.parametrize(
    ("entrypoint", "failure_kind", "exc_type"),
    [
        ("validate_only", "l2_schema", SchemaValidationException),
        ("validate_only", "l1_intent", InvalidIntentException),
        ("validate_only", "l3_defi", MaliciousPayloadException),
        ("validate_and_simulate", "l2_schema", SchemaValidationException),
        ("validate_and_simulate", "l1_intent", InvalidIntentException),
        ("validate_and_simulate", "l3_defi", MaliciousPayloadException),
    ],
)
def test_validate_paths_failure_family_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
    entrypoint: str,
    failure_kind: str,
    exc_type: type[BaseException],
) -> None:
    # L1 intent failures must exercise the real ``IntentValidator`` (success patches stub it out).
    if failure_kind != "l1_intent":
        _install_success_monkeypatches(monkeypatch)
    if failure_kind == "l2_schema":

        def _schema_boom(self: Any, draft: Any) -> bool:  # type: ignore[no-untyped-def]
            raise SchemaValidationException(
                human_readable_reason="contract schema fail",
                context={"layer": "L2", "reason": "contract_schema_fail"},
            )

        monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", _schema_boom)
    elif failure_kind == "l3_defi":

        def _defi_boom(self: Any, draft: Any) -> bool:  # type: ignore[no-untyped-def]
            raise MaliciousPayloadException(
                human_readable_reason="contract defi fail",
                context={"layer": "L3", "reason": "contract_defi_fail"},
            )

        monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", _defi_boom)

    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    intent = "swap" if failure_kind != "l1_intent" else "transfer"

    if entrypoint == "validate_only":
        with pytest.raises(exc_type) as sync_e:
            guard.validate_only(intent, payload)
        with pytest.raises(exc_type) as async_e:
            asyncio.run(guard.async_validate_only(intent, payload))
    else:
        with pytest.raises(exc_type) as sync_e:
            guard.validate_and_simulate(intent, payload)
        with pytest.raises(exc_type) as async_e:
            asyncio.run(guard.async_validate_and_simulate(intent, payload))

    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_validate_and_simulate_l4_failure_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _l4_boom_sync(self: Any) -> int:  # type: ignore[no-untyped-def]
        raise RPCUnavailableException(context={"layer": "L4", "reason": "contract_l4_fail"})

    async def _l4_boom_async(self: Any) -> int:  # type: ignore[no-untyped-def]
        raise RPCUnavailableException(context={"layer": "L4", "reason": "contract_l4_fail"})

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", _l4_boom_sync)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _l4_boom_async)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    with pytest.raises(RPCUnavailableException) as sync_e:
        guard.validate_and_simulate("swap", payload)
    with pytest.raises(RPCUnavailableException) as async_e:
        asyncio.run(guard.async_validate_and_simulate("swap", payload))
    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_validate_and_simulate_l5_failure_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _l5_boom(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        raise SimulationFailedException(
            human_readable_reason="contract l5 fail",
            context={"layer": "L5", "reason": "contract_l5_fail"},
        )

    async def _l5_boom_a(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        raise SimulationFailedException(
            human_readable_reason="contract l5 fail",
            context={"layer": "L5", "reason": "contract_l5_fail"},
        )

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate", _l5_boom)
    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _l5_boom_a)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    with pytest.raises(SimulationFailedException) as sync_e:
        guard.validate_and_simulate("swap", payload)
    with pytest.raises(SimulationFailedException) as async_e:
        asyncio.run(guard.async_validate_and_simulate("swap", payload))
    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_validate_and_simulate_policy_failure_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)

    def _policy_boom(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        raise LirixPolicyViolationException(
            human_readable_reason="contract policy fail",
            context={"layer": "policy", "reason": "contract_policy_fail"},
        )

    monkeypatch.setattr("lirix._facade.Lirix._run_policy_audit", _policy_boom)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    with pytest.raises(LirixPolicyViolationException) as sync_e:
        guard.validate_and_simulate("swap", payload)
    with pytest.raises(LirixPolicyViolationException) as async_e:
        asyncio.run(guard.async_validate_and_simulate("swap", payload))
    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_simulate_only_after_prior_validate_l4_failure_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    sess = ValidationSession()
    guard.validate_only("swap", payload, session=sess)

    def _l4_boom_sync(self: Any) -> int:  # type: ignore[no-untyped-def]
        raise RPCUnavailableException(context={"layer": "L4", "reason": "contract_l4_fail"})

    async def _l4_boom_async(self: Any) -> int:  # type: ignore[no-untyped-def]
        raise RPCUnavailableException(context={"layer": "L4", "reason": "contract_l4_fail"})

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", _l4_boom_sync)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _l4_boom_async)
    with pytest.raises(RPCUnavailableException) as sync_e:
        guard.simulate_only(payload, session=sess)
    with pytest.raises(RPCUnavailableException) as async_e:
        asyncio.run(guard.async_simulate_only(payload, session=sess))
    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_simulate_only_after_prior_validate_l5_failure_sync_async_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    sess = ValidationSession()
    guard.validate_only("swap", payload, session=sess)

    def _l5_boom(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        raise SimulationFailedException(
            human_readable_reason="contract l5 fail",
            context={"layer": "L5", "reason": "contract_l5_fail"},
        )

    async def _l5_boom_a(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        raise SimulationFailedException(
            human_readable_reason="contract l5 fail",
            context={"layer": "L5", "reason": "contract_l5_fail"},
        )

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate", _l5_boom)
    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _l5_boom_a)
    with pytest.raises(SimulationFailedException) as sync_e:
        guard.simulate_only(payload, session=sess)
    with pytest.raises(SimulationFailedException) as async_e:
        asyncio.run(guard.async_simulate_only(payload, session=sess))
    _assert_enriched_failure_context_parity(sync_e.value, async_e.value)


def test_simulate_only_prior_validate_required_sync_async_parity() -> None:
    guard = Lirix(_simulate_gate_config())
    payload = _valid_l1_payload()
    with pytest.raises(ConfigurationGuardException) as sync_e:
        guard.simulate_only(payload)
    with pytest.raises(ConfigurationGuardException) as async_e:
        asyncio.run(guard.async_simulate_only(payload))
    assert (
        sync_e.value.context.get("reason")
        == async_e.value.context.get("reason")
        == "simulate_only_prior_validate_required"
    )
