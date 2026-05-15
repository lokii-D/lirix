"""Regression: run_full runs L1–L3 twice (post pre_simulation) on the same draft; simulate_only unchanged."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from lirix.core.client_components import FailureContextEnricher
from lirix.core.constants import (
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
)
from lirix.core.exceptions import LirixBaseException, SchemaValidationException
from lirix.core.orchestrator import LirixPipelineOrchestrator
from lirix.core.session import ValidationSession


@dataclass
class _FakeEvidence:
    def validate_and_simulate(self, **kwargs: Any) -> dict[str, Any]:
        return {"contract": "evidence_v2"}


@dataclass
class _FakePipeline:
    failures: FailureContextEnricher = field(default_factory=FailureContextEnricher)
    evidence: _FakeEvidence = field(default_factory=_FakeEvidence)


class _RpcStub:
    def evidence_snapshot(self) -> dict[str, Any]:
        return {"rpc": 1}


class _FakeOrchestratorClient:
    """Minimal `OrchestratorClient` for `run_full` call-order and fail-closed tests."""

    def __init__(self) -> None:
        self.hooks = SimpleNamespace(bind_trace_recorder=lambda _r: None)
        self._pipeline = _FakePipeline()
        self.events: list[str] = []
        self.l1_l3_payloads: list[Mapping[str, Any]] = []
        self.l1_l3_calls = 0
        self.reject_second_l1_l3 = False

    def _ensure_hook_trace_binding(self) -> None:
        self.events.append("ensure_hook_trace")

    def _migration_modes(self) -> dict[str, str]:
        return {}

    def _config_fingerprint(self) -> str:
        return "fp"

    def _registry_closure_digest(self) -> str:
        return "reg"

    def _replay_proof(self) -> dict[str, Any]:
        return {}

    def _artifact_digests_base(self) -> dict[str, str]:
        return {}

    def _artifact_digests_with_rpc(self, *, rpc_snapshot: Mapping[str, Any]) -> dict[str, str]:
        return {"with_rpc": "1"}

    def _run_l1_l3_validation(
        self, *, intent: str, payload: Mapping[str, Any], recorder: Any
    ) -> None:
        self.l1_l3_calls += 1
        self.l1_l3_payloads.append(payload)
        self.events.append(f"l1_l3#{self.l1_l3_calls}")
        if self.reject_second_l1_l3 and self.l1_l3_calls == 2:
            raise SchemaValidationException(
                human_readable_reason="second pass failed",
                context={"reason": "schema_regression"},
            )

    def _mark_session_l1_l3_ok(self, sess: Any) -> None:
        self.events.append("mark_l1_l3_ok")
        sess.state["l1_l3_ok"] = True

    def _build_rpc_manager(self) -> _RpcStub:
        self.events.append("build_rpc")
        return _RpcStub()

    def _l4_orchestration_details(self, *, rpc: Any, block_number: int) -> Mapping[str, Any]:
        return {"bn": block_number}

    def _build_sandbox_simulator(self) -> object:
        self.events.append("build_sandbox")
        return object()

    def _run_policy_audit(self, **kwargs: Any) -> dict[str, Any]:
        self.events.append("policy_audit")
        return {}

    def _record_full_pipeline_success(self, **kwargs: Any) -> dict[str, Any]:
        self.events.append("record_full_success")
        return {"steps": []}

    def _build_result(self, **kwargs: Any) -> dict[str, Any]:
        self.events.append("build_result")
        return {"status": kwargs.get("status"), "decision": kwargs.get("decision")}


def _async_ok_hooks() -> list[dict[str, Any]]:
    return []


async def _run_full_with_client(
    *,
    client: _FakeOrchestratorClient,
    hook_log: list[str],
    sess: ValidationSession | None = None,
    fail_second_l1_l3: bool = False,
) -> dict[str, Any]:
    client.reject_second_l1_l3 = fail_second_l1_l3

    async def invoke_hooks(hook_point: str, **kwargs: Any) -> list[dict[str, Any]]:
        hook_log.append(hook_point)
        return _async_ok_hooks()

    async def reconcile(_rpc: Any) -> int:
        client.events.append("reconcile")
        return 42

    async def get_web3(_rpc: Any) -> object:
        client.events.append("get_web3")
        return object()

    async def simulate(_w3: Any, _draft: Mapping[str, Any], _bn: int, _so: Any) -> dict[str, Any]:
        client.events.append("simulate")
        return {"simulation_ok": True, "return_data": "0x"}

    orch = LirixPipelineOrchestrator()
    return await orch.run_full(
        client=client,
        kind="validate_and_simulate",
        decision_rationale="test",
        finalization_note="test done",
        intent="swap",
        payload={"to": "0x1", "data": "0x"},
        state_overrides=None,
        security_policy=None,
        session=sess,
        invoke_hooks=invoke_hooks,
        reconcile=reconcile,
        get_web3=get_web3,
        simulate=simulate,
        agent_feedback_stage="validate_and_simulate",
    )


def test_run_full_invokes_l1_l3_after_pre_simulation_before_l4() -> None:
    client = _FakeOrchestratorClient()
    hook_log: list[str] = []

    out = asyncio.run(_run_full_with_client(client=client, hook_log=hook_log))

    assert out.get("status") == "approved"
    assert hook_log[0] == HOOK_PRE_VALIDATE
    assert hook_log[1] == HOOK_PRE_SIMULATION
    assert HOOK_POST_SIMULATION in hook_log and HOOK_POST_VALIDATE in hook_log

    ev = client.events
    pre_rpc = ev.index("build_rpc")
    assert ev.index("l1_l3#1") < ev.index("mark_l1_l3_ok") < ev.index("l1_l3#2") < pre_rpc
    assert ev.index("l1_l3#2") < ev.index("reconcile") < ev.index("get_web3") < ev.index("simulate")
    assert client.l1_l3_calls == 2
    assert client.l1_l3_payloads[0] is client.l1_l3_payloads[1]
    assert client.l1_l3_payloads[0] == {"to": "0x1", "data": "0x"}


def test_run_full_second_l1_l3_failure_fail_closed_records_audit_trail() -> None:
    """Second L1–L3 blocks L4/L5 and still runs the standard LirixBaseException → _record_failure audit path."""
    client = _FakeOrchestratorClient()
    hook_log: list[str] = []
    sess = ValidationSession()

    with pytest.raises(LirixBaseException) as exc_info:
        asyncio.run(
            _run_full_with_client(
                client=client, hook_log=hook_log, sess=sess, fail_second_l1_l3=True
            )
        )

    exc = exc_info.value
    assert isinstance(exc, SchemaValidationException)

    assert hook_log[:2] == [HOOK_PRE_VALIDATE, HOOK_PRE_SIMULATION]
    assert HOOK_POST_SIMULATION not in hook_log and HOOK_POST_VALIDATE not in hook_log
    assert "build_rpc" not in client.events
    assert "reconcile" not in client.events
    assert "get_web3" not in client.events
    assert "simulate" not in client.events
    assert "policy_audit" not in client.events
    assert "record_full_success" not in client.events
    assert "build_result" not in client.events
    assert client.l1_l3_calls == 2

    rejected_traces = [
        item
        for item in sess.timeline
        if isinstance(item, dict)
        and item.get("kind") == "validate_and_simulate"
        and item.get("status") == "rejected"
    ]
    assert len(rejected_traces) == 1

    decisions = sess.decision_log()
    assert decisions, "blocked pipeline must emit a session decision"
    last_decision = decisions[-1]
    assert last_decision.get("payload", {}).get("verdict") == "blocked"
    dec_ctx = last_decision.get("payload", {}).get("details", {}).get("context", {})
    assert dec_ctx.get("reason") == "schema_regression"

    ctx = getattr(exc, "context", None)
    assert isinstance(ctx, dict)
    assert ctx.get("reason") == "schema_regression"
    af = ctx.get("agent_feedback")
    assert isinstance(af, dict) and af, "agent_feedback must be populated on rejection"
    assert af.get("layer") not in (None, "")
    assert af.get("failure_type") not in (None, "")
    assert af.get("reason_code") not in (None, "")
    fp = ctx.get("failure_protocol")
    assert isinstance(fp, dict) and fp, "failure_protocol must be attached for audit joins"
    assert "failure_type_canonical" in fp or fp.get("failure_type")


def test_run_full_l1_l3_ok_set_after_first_pass_semantics() -> None:
    """Session gate: l1_l3_ok means initial L1–L3 success; post–pre_simulation run is a re-check."""
    client = _FakeOrchestratorClient()
    hook_log: list[str] = []
    sess = ValidationSession()

    asyncio.run(_run_full_with_client(client=client, hook_log=hook_log, sess=sess))

    assert sess.state.get("l1_l3_ok") is True
    assert client.events.index("mark_l1_l3_ok") < client.events.index("l1_l3#2")


def test_run_full_second_l1_l3_failure_leaves_l1_l3_ok_true() -> None:
    """Re-validation failure blocks L4/L5 but does not clear the session gate flag."""
    client = _FakeOrchestratorClient()
    sess = ValidationSession()

    with pytest.raises(SchemaValidationException):
        asyncio.run(
            _run_full_with_client(client=client, hook_log=[], sess=sess, fail_second_l1_l3=True)
        )

    assert sess.state.get("l1_l3_ok") is True


def test_simulate_only_does_not_invoke_l1_l3_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """simulate_only stays on the L4–L5 path only (no L1–L3 revalidation in run_simulate)."""
    from lirix import Lirix

    calls: list[int] = []

    def _counting_run_l1_l3(self: Any, **kwargs: Any) -> None:
        calls.append(1)

    monkeypatch.setattr("lirix._facade.Lirix._run_l1_l3_validation", _counting_run_l1_l3)
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self: Any) -> int:  # type: ignore[no-untyped-def]
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

    async def _simulate_async(
        self: Any, payload: Any, *, async_web3: Any, block_number: int, state_overrides: Any = None
    ) -> dict[str, Any]:
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)

    guard = Lirix(rpc_urls=["https://example.invalid"])
    guard.simulate_only({"to": "0x1", "data": "0x"})
    assert calls == []
