from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session import ValidationSession, verify_replay_bundle


def _base_bundle() -> dict:
    # Minimal structurally valid bundle; individual tests mutate one field.
    return {
        "bundle_version": "2.0",
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "replay_proof": {},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": {
            "session_id": "s",
            "created_at": "t",
            "correlation_ids": [],
            "timeline": [],
            "state": {},
        },
    }


def test_verify_replay_bundle_rejects_non_mapping_payload() -> None:
    b = _base_bundle()
    b["payload"] = "x"
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_malformed"


def test_verify_replay_bundle_rejects_non_list_timeline() -> None:
    b = _base_bundle()
    b["payload"]["timeline"] = "x"
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_malformed"


def test_verify_replay_bundle_rejects_non_mapping_timeline_entry() -> None:
    b = _base_bundle()
    b["payload"]["timeline"] = ["x"]
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_malformed"


def test_verify_replay_bundle_rejects_invalid_event_type() -> None:
    b = _base_bundle()
    b["payload"]["timeline"] = [{"kind": "session_event", "event_type": "nope", "status": "info"}]
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_timeline_event_type"


def test_verify_replay_bundle_rejects_invalid_event_status() -> None:
    b = _base_bundle()
    b["payload"]["timeline"] = [{"kind": "session_event", "event_type": "plan", "status": "bad"}]
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_timeline_status"


def test_verify_replay_bundle_rejects_timeline_size_mismatch() -> None:
    b = _base_bundle()
    b["payload"]["timeline"] = []
    b["timeline_size"] = 1
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_timeline_size_mismatch"


def test_verify_replay_bundle_rejects_registry_closure_digest_malformed() -> None:
    b = _base_bundle()
    b["registry_closure_digest"] = "x"
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_registry_closure_digest_malformed"


def test_verify_replay_bundle_rejects_artifact_digests_not_object() -> None:
    b = _base_bundle()
    b["artifact_digests"] = "x"
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_artifact_digests_malformed"


def test_verify_replay_bundle_rejects_non_ext_artifact_digest_keys() -> None:
    """Mirrors ``test_session.test_replay_bundle_rejects_disallowed_artifact_digest_key`` for malformed-suite audit."""
    b = _base_bundle()
    b["artifact_digests"] = {"custom_not_ext_key": "f" * 64}
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b)
    assert exc_info.value.context.get("reason") == "replay_bundle_artifact_digests_key_not_allowed"


def test_verify_replay_bundle_strict_requires_replay_proof_keys() -> None:
    b = _base_bundle()
    b["replay_proof"] = {"chain_registry_digest": "a" * 64}
    with pytest.raises(ConfigurationGuardException) as exc_info:
        verify_replay_bundle(b, enforce_replay_proof_strict=True)
    assert exc_info.value.context.get("reason") == "replay_bundle_replay_proof_missing_keys"


def test_verify_replay_bundle_strict_full_contract_passes() -> None:
    s = ValidationSession(workflow_strict=True)
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "x", "steps": []},
        status="ok",
        replay_proof={
            "chain_registry_digest": "a" * 64,
            "decoder_registry_digest": "b" * 64,
            "registry_version": "v1",
            "registry_source": "test",
        },
    )
    s.record_plan(objective="o")
    s.record_draft(label="d", content={})
    s.record_tool_call(tool_name="t", input_summary={})
    s.record_decision(verdict="approved", rationale="ok")
    s.finalize(outcome="ok")
    s.record_event(event_type="annotation", payload={"note": "post-finalize-annotation"})
    bundle = s.replay_bundle()
    verify_replay_bundle(
        bundle,
        enforce_workflow_strict=True,
        enforce_replay_proof_strict=True,
    )
