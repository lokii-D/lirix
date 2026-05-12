from __future__ import annotations

import pytest
from lirix import Lirix
from lirix.core import ExecutionPlan, ValidationSession
from lirix.core.canonical_taxonomy import lookup_reason_taxon
from lirix.core.constants import AGENT_FEEDBACK_REASON_TIMEOUT
from lirix.core.exceptions import ConfigurationGuardException, InvalidIntentException
from lirix.core.failure_protocol import (
    FAILURE_PROTOCOL_SCHEMA_VERSION,
    build_failure_protocol_from_agent_feedback,
    resolve_failure_protocol_to_agent_feedback,
)
from lirix.core.forensic_verifier import verify_forensic_bundle
from lirix.core.session import verify_replay_bundle

_SESSION_PIPELINE_PAYLOAD = {"to": "0x1111111111111111111111111111111111111111", "data": "0x"}


def _patch_success_pipeline_sync_async(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
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
        },
    )

    async def _simulate_async(self: object, payload: object, **kwargs: object) -> dict[str, object]:
        block_number = kwargs.get("block_number", 0)
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)


def test_validation_session_links_multiple_traces(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])
    session = ValidationSession()

    _patch_success_pipeline_sync_async(monkeypatch)

    out1 = guard.validate_and_simulate("swap", _SESSION_PIPELINE_PAYLOAD, session=session)
    out2 = guard.validate_and_simulate("swap", _SESSION_PIPELINE_PAYLOAD, session=session)

    assert out1["validation_session"]["session_id"] == session.session_id
    assert out2["validation_session"]["session_id"] == session.session_id
    assert len(out2["validation_session"]["correlation_ids"]) == 2
    timeline = out2["validation_session"]["timeline"]
    trace_items = [
        e for e in timeline if isinstance(e, dict) and e.get("kind") == "validate_and_simulate"
    ]
    assert len(trace_items) == 2
    assert out2["agent_feedback"]["reason_code"] == "LIRIX_REASON_OK"
    assert out2["agent_feedback"]["retry_allowed"] is False


def test_validation_session_records_lifecycle_events() -> None:
    session = ValidationSession()
    session.record_plan(objective="ship safe tx", constraints=["fail-closed", "no secrets"])
    session.record_draft(label="draft-1", content={"to": "0x1", "data": "0x"})
    session.record_tool_call(
        tool_name="rpc", input_summary={"nodes": 3}, output_summary={"ok": 2}, ok=True
    )
    session.record_decision(
        verdict="approved", rationale="meets policy", details={"policy_id": "p"}
    )
    session.finalize(outcome="ok", notes="ready to sign")

    snap = session.snapshot()
    assert snap["timeline"]
    kinds = [e.get("kind") for e in snap["timeline"] if isinstance(e, dict)]
    assert "session_event" in kinds
    assert snap["decision_log"]
    assert session.replay_bundle()["bundle_digest"]
    assert isinstance(session.forensic_bundle()["error_codes"], list)
    verify_forensic_bundle(session.forensic_bundle(), enforce_replay_link=True)


def test_verify_forensic_bundle_replay_bundle_digest_binding_passes() -> None:
    session = ValidationSession()
    session.record_plan(objective="ship", constraints=["c"])
    session.record_draft(label="d1", content={"x": 1})
    session.record_decision(verdict="approved", rationale="ok")
    session.finalize(outcome="ok")
    rb = session.replay_bundle()
    fb = session.forensic_bundle()
    verify_forensic_bundle(fb, enforce_replay_link=True, replay_bundle=rb)


def test_verify_forensic_bundle_rejects_replay_bundle_digest_mismatch() -> None:
    session = ValidationSession()
    session.record_plan(objective="ship", constraints=["c"])
    session.record_draft(label="d1", content={"x": 1})
    session.record_decision(verdict="approved", rationale="ok")
    session.finalize(outcome="ok")
    rb = session.replay_bundle()
    fb = dict(session.forensic_bundle())
    fb["replay_bundle_digest"] = "1" * 64
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_forensic_bundle(fb, enforce_replay_link=True, replay_bundle=rb)
    assert exc_info.value.context.get("reason") == "forensic_replay_bundle_digest_mismatch"


def test_validation_session_trace_summary_handles_non_list_and_non_dict_steps() -> None:
    session = ValidationSession()
    session.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "c", "steps": "not-a-list"},
        status="ok",
    )
    session.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "c2", "steps": ["x", {"status": "ok"}]},
        status="ok",
        include_full_trace=True,
        extra={"k": "v"},
    )


def test_validation_session_link_trace_dedup_and_empty() -> None:
    session = ValidationSession()
    session.link_trace("")
    session.link_trace("c1")
    session.link_trace("c1")
    assert session.snapshot()["correlation_ids"] == ["c1"]


def test_validation_session_forensic_bundle_handles_non_dict_payload_shapes() -> None:
    session = ValidationSession()
    session.timeline.append(
        {"kind": "session_event", "status": "rejected", "payload": "not-a-dict"}
    )
    session.timeline.append(
        {"kind": "session_event", "status": "rejected", "payload": {"details": "x"}}
    )
    fb = session.forensic_bundle()
    assert fb["rejected_events"]
    assert fb["raw_error_codes"] == fb["error_codes"]
    assert "last_rejected_step" in fb
    assert "fatal_hook_summary" in fb


def test_forensic_bundle_extracts_hook_fatal_summary_from_decision_context() -> None:
    session = ValidationSession()
    session.record_decision(
        verdict="blocked",
        rationale="blocked",
        details={
            "context": {
                "layer": "hooks",
                "reason": "hook_blocked",
                "error_code": "LIRIX_ERR_HOOK_EXECUTION",
                "hook_result": {
                    "hook_point": "pre_validate",
                    "error_code": "LIRIX_HOOK_DECISION_REJECTED",
                    "error_type": "policy_rejection",
                    "failure_level": "fatal",
                },
            }
        },
    )
    fb = session.forensic_bundle()
    assert fb["last_rejected_step"]["layer"] == "hooks"
    assert fb["fatal_hook_summary"]["failure_level"] == "fatal"


def test_lirix_records_decision_and_finalize_events(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])
    session = ValidationSession()

    _patch_success_pipeline_sync_async(monkeypatch)

    out = guard.validate_and_simulate("swap", _SESSION_PIPELINE_PAYLOAD, session=session)
    timeline = out["validation_session"]["timeline"]
    event_types = [
        e.get("event_type")
        for e in timeline
        if isinstance(e, dict) and e.get("kind") == "session_event"
    ]
    assert "decision" in event_types
    # 外部传入的 ValidationSession 不自动 finalize，以便多轮 trace 共存
    assert "finalize" not in event_types
    assert out["agent_feedback"]["failure_type"] == "none"
    assert out["replay_bundle"]["bundle_digest"]
    assert isinstance(out["forensic_bundle"]["error_codes"], list)


def test_validate_only_failure_maps_reason_code_for_agent_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])

    def _raise(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(
            human_readable_reason="timed out",
            context={"layer": "L1", "reason": "timeout"},
        )

    monkeypatch.setattr("lirix._client_core.IntentValidator.validate", _raise)

    with pytest.raises(InvalidIntentException) as exc_info:
        guard.validate_only("swap", {"to": "0x1", "data": "0x"})

    feedback = exc_info.value.context.get("agent_feedback", {})
    assert feedback.get("reason_code") == "LIRIX_REASON_TIMEOUT"
    assert feedback.get("retry_allowed") is True


def test_validate_and_simulate_failure_context_contains_validation_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])

    def _raise(*args: object, **kwargs: object) -> None:
        raise InvalidIntentException(
            human_readable_reason="timed out",
            context={"layer": "L1", "reason": "timeout"},
        )

    monkeypatch.setattr("lirix._client_core.IntentValidator.validate", _raise)

    with pytest.raises(InvalidIntentException) as exc_info:
        guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})

    ctx = exc_info.value.context
    assert isinstance(ctx.get("validation_session"), dict)
    assert isinstance(ctx.get("replay_bundle"), dict)
    assert isinstance(ctx.get("forensic_bundle"), dict)
    assert isinstance(ctx.get("failure_protocol"), dict)


def test_validation_session_workflow_strict_requires_ordered_events() -> None:
    s = ValidationSession(workflow_strict=True)
    with pytest.raises(ConfigurationGuardException) as exc_info:
        s.record_draft(label="d", content={})
    assert exc_info.value.context.get("reason") == "session_fsm_workflow_order"


def test_replay_bundle_v2_verify_roundtrip_with_registry_closure_digest() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "x",
            "steps": [{"status": "ok", "layer": "L1", "stage": "a", "details": {}}],
        },
        status="ok",
        registry_closure_digest="d" * 64,
        replay_proof={"chain_registry_digest": "a" * 64, "decoder_registry_digest": "b" * 64},
    )
    rb = s.replay_bundle()
    assert rb.get("registry_closure_digest") == "d" * 64
    verify_replay_bundle(rb)


def test_record_trace_rejects_invalid_status() -> None:
    s = ValidationSession()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        s.record_trace(
            kind="validate_only",
            trace={"trace_version": "1.0", "correlation_id": "c", "steps": []},
            status="info",  # type: ignore[arg-type]
        )
    assert exc_info.value.context.get("reason") == "session_trace_status_invalid"


def test_record_event_rejects_invalid_status_and_event_type() -> None:
    s = ValidationSession()
    with pytest.raises(ConfigurationGuardException):
        s.record_event(event_type="unknown", payload={}, status="info")  # type: ignore[arg-type]
    with pytest.raises(ConfigurationGuardException):
        s.record_event(event_type="annotation", payload={}, status="bad")  # type: ignore[arg-type]


def test_record_decision_rejects_unknown_verdict() -> None:
    s = ValidationSession()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        s.record_decision(verdict="allow", rationale="x")  # type: ignore[arg-type]
    assert exc_info.value.context.get("reason") == "session_decision_verdict_invalid"


def test_record_decision_blocked_updates_session_outcome() -> None:
    s = ValidationSession()
    s.record_decision(verdict="blocked", rationale="policy")
    assert s.state["session_outcome"] == "rejected"


def test_finalize_non_ok_marks_session_outcome_rejected() -> None:
    s = ValidationSession()
    s.finalize(outcome="aborted")
    assert s.state["session_outcome"] == "rejected"


def test_session_outcome_monotonic_rejected_after_info_events() -> None:
    s = ValidationSession()
    s.record_plan(objective="o", constraints=[])
    assert s.state["session_outcome"] == "info"
    s.record_decision(verdict="blocked", rationale="n")
    assert s.state["session_outcome"] == "rejected"


def test_replay_bundle_rejects_non_string_registry_version() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "x", "steps": []},
        status="ok",
        replay_proof={"chain_registry_digest": "a" * 64, "registry_version": 1},
    )
    rb = s.replay_bundle()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(rb)
    assert exc_info.value.context.get("reason") == "replay_bundle_replay_proof_malformed"


def test_replay_bundle_rejects_disallowed_artifact_digest_key() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "x", "steps": []},
        status="ok",
        artifact_digests={"custom_digest": "f" * 64},
    )
    rb = s.replay_bundle()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(rb)
    assert exc_info.value.context.get("reason") == "replay_bundle_artifact_digests_key_not_allowed"


def test_replay_bundle_detects_trace_metadata_drift() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "x1", "steps": []},
        status="ok",
        config_fingerprint="a" * 64,
    )
    s.record_trace(
        kind="simulate_only",
        trace={"trace_version": "1.0", "correlation_id": "x2", "steps": []},
        status="ok",
        config_fingerprint="b" * 64,
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        s.replay_bundle()
    assert exc_info.value.context.get("reason") == "replay_bundle_metadata_drift"


def test_failure_protocol_agent_feedback_bridge_roundtrip() -> None:
    af = {
        "schema_version": "1.0",
        "failure_type": "security_rejection",
        "layer": "L1",
        "reason_code": "LIRIX_REASON_TIMEOUT",
        "retry_allowed": True,
        "remediation": "retry later",
        "details": {"correlation_id": "c"},
    }
    ctx: dict = {"layer": "L1", "reason": "timeout", "agent_feedback": af}
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L1",
        failure_type="timeout",
        agent_feedback=af,
        details=ctx,
    )
    assert fp["schema_version"] == FAILURE_PROTOCOL_SCHEMA_VERSION
    assert fp["retryable"] is True
    back = resolve_failure_protocol_to_agent_feedback(fp)
    assert back["reason_code"] == "LIRIX_REASON_TIMEOUT"


def test_build_failure_protocol_prefers_resolution_for_agent_over_remediation() -> None:
    af = {
        "schema_version": "1.0",
        "failure_type": "timeout",
        "layer": "L4",
        "reason_code": AGENT_FEEDBACK_REASON_TIMEOUT,
        "retry_allowed": True,
        "remediation": "from remediation field",
        "resolution_for_agent": "use this first",
        "details": {},
    }
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L4",
        failure_type="timeout",
        agent_feedback=af,
    )
    assert fp["repair_hint"] == "use this first"


def test_build_failure_protocol_resolution_in_details_over_remediation() -> None:
    af = {
        "schema_version": "1.0",
        "failure_type": "timeout",
        "layer": "L4",
        "reason_code": AGENT_FEEDBACK_REASON_TIMEOUT,
        "retry_allowed": True,
        "remediation": "remediation body",
        "details": {"resolution_for_agent": "nested wins"},
    }
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L4",
        failure_type="timeout",
        agent_feedback=af,
    )
    assert fp["repair_hint"] == "nested wins"


def test_build_failure_protocol_falls_back_to_taxon_remediation_without_resolution_or_remediation() -> (
    None
):
    af = {
        "schema_version": "1.0",
        "failure_type": "timeout",
        "layer": "L4",
        "reason_code": AGENT_FEEDBACK_REASON_TIMEOUT,
        "retry_allowed": True,
        "details": {},
    }
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L4",
        failure_type="timeout",
        agent_feedback=af,
    )
    assert (
        fp["repair_hint"] == lookup_reason_taxon(AGENT_FEEDBACK_REASON_TIMEOUT).default_remediation
    )


def test_replay_bundle_v2_verify_roundtrip() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "x",
            "steps": [{"status": "ok", "layer": "L1", "stage": "a", "details": {}}],
        },
        status="ok",
        migration_modes={"a": "b"},
        config_fingerprint="a" * 64,
    )
    rb = s.replay_bundle()
    assert rb["bundle_version"] == "2.0"
    verify_replay_bundle(rb)


def test_replay_bundle_v2_verify_rejects_malformed_digest_fields() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "x",
            "steps": [{"status": "ok", "layer": "L1", "stage": "a", "details": {}}],
        },
        status="ok",
        config_fingerprint="a" * 64,
        artifact_digests={"config_snapshot_digest": "b" * 64},
    )
    rb = s.replay_bundle()
    rb["config_fingerprint"] = "not-a-digest"
    import hashlib
    import json

    canonical = json.dumps(
        {
            "bundle_version": "2.0",
            "migration_modes": rb.get("migration_modes") or {},
            "config_fingerprint": rb.get("config_fingerprint"),
            "last_trace_digest": rb.get("last_trace_digest"),
            "artifact_digests": rb.get("artifact_digests") or {},
            "replay_proof": rb.get("replay_proof") or {},
            "payload": rb.get("payload"),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    rb["bundle_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(rb)
    assert exc_info.value.context.get("reason") == "replay_bundle_config_fingerprint_malformed"


def test_verify_replay_bundle_rejects_session_mutations_after_finalize() -> None:
    bundle = {
        "bundle_version": "2.0",
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "payload": {
            "session_id": "s1",
            "created_at": "now",
            "correlation_ids": [],
            "timeline": [
                {
                    "kind": "session_event",
                    "event_type": "finalize",
                    "status": "ok",
                    "payload": {"outcome": "ok"},
                },
                {
                    "kind": "session_event",
                    "event_type": "decision",
                    "status": "rejected",
                    "payload": {"verdict": "blocked"},
                },
            ],
            "state": {},
        },
    }
    import hashlib
    import json

    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    bundle["bundle_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(bundle)
    assert exc_info.value.context.get("reason") == "replay_bundle_timeline_order"


def test_verify_replay_bundle_rejects_duplicate_finalize() -> None:
    bundle = {
        "bundle_version": "2.0",
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "timeline_size": 2,
        "decision_count": 0,
        "payload": {
            "session_id": "s1",
            "created_at": "now",
            "correlation_ids": [],
            "timeline": [
                {"kind": "session_event", "event_type": "finalize", "status": "ok", "payload": {}},
                {"kind": "session_event", "event_type": "finalize", "status": "ok", "payload": {}},
            ],
            "state": {},
        },
    }
    import hashlib
    import json

    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    bundle["bundle_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(bundle)
    assert exc_info.value.context.get("reason") == "replay_bundle_timeline_finalize_duplicate"


def test_verify_replay_bundle_rejects_decision_count_mismatch() -> None:
    bundle = {
        "bundle_version": "2.0",
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "timeline_size": 1,
        "decision_count": 1,
        "payload": {
            "session_id": "s1",
            "created_at": "now",
            "correlation_ids": [],
            "timeline": [
                {"kind": "session_event", "event_type": "plan", "status": "info", "payload": {}},
            ],
            "state": {},
        },
    }
    import hashlib
    import json

    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    bundle["bundle_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(bundle)
    assert exc_info.value.context.get("reason") == "replay_bundle_decision_count_mismatch"


def test_verify_replay_bundle_enforce_workflow_strict_rejects_missing_prereq() -> None:
    bundle = {
        "bundle_version": "2.0",
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "timeline_size": 1,
        "decision_count": 1,
        "payload": {
            "session_id": "s1",
            "created_at": "now",
            "correlation_ids": [],
            "timeline": [
                {
                    "kind": "session_event",
                    "event_type": "decision",
                    "status": "rejected",
                    "payload": {},
                },
            ],
            "state": {},
        },
    }
    import hashlib
    import json

    canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str)
    bundle["bundle_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(bundle, enforce_workflow_strict=True)
    assert exc_info.value.context.get("reason") == "session_fsm_workflow_order"


def test_validation_session_binds_execution_plan() -> None:
    session = ValidationSession()
    plan = ExecutionPlan(
        plan_id="plan-1",
        objective="secure swap flow",
        steps=["validate_only", "validate_and_simulate"],
        retry_budget=1,
        constraints=["fail-closed"],
    )
    session.bind_execution_plan(plan)
    snap = session.snapshot()
    assert snap["state"]["execution_plan"]["plan_id"] == "plan-1"
