# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Targeted branch coverage for pyproject fail_under=100 on lirix/."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping, cast

import pytest
from lirix import Lirix
from lirix.core import constants as lirix_constants
from lirix.core.canonical_taxonomy import (
    canonical_reason_from_rpc_reason,
    lookup_reason_taxon,
)
from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_WARN_PATCH_TARGET_SHADOW, LIRIX_ERR_LEGACY_ERROR
from lirix.core.evidence import SecurityTrace
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.failure_protocol import resolve_failure_protocol_to_agent_feedback
from lirix.core.forensic_verifier import verify_forensic_bundle
from lirix.core.hook_contract import HookPatch
from lirix.core.hook_manager import HookManager
from lirix.core.session import (
    FORENSIC_BUNDLE_VERSION,
    REPLAY_BUNDLE_VERSION,
    ValidationSession,
    verify_replay_bundle,
)
from lirix.core.session_fsm import SessionEvent, SessionFSM
from lirix.integrations.langchain.tool import LirixSecurityValidator
from lirix.layers.l4_rpc_manager import RPCManager


def _minimal_forensic_bundle() -> dict[str, Any]:
    return {
        "forensic_version": FORENSIC_BUNDLE_VERSION,
        "replay_bundle_version": REPLAY_BUNDLE_VERSION,
        "session_id": "s1",
        "rejected_events": [],
        "error_codes": [],
        "raw_error_codes": [],
        "canonical_error_codes": [],
        "replay_bundle_digest": "a" * 64,
    }


def test_lookup_reason_taxon_blank_falls_through_to_unknown() -> None:
    taxon = lookup_reason_taxon("")
    assert taxon.reason_code == "LIRIX_REASON_UNKNOWN"


def test_canonical_reason_from_rpc_reason_blank() -> None:
    assert canonical_reason_from_rpc_reason("") is None


def test_canonicalize_error_code_empty_token() -> None:
    assert lirix_constants.canonicalize_error_code("") == LIRIX_ERR_LEGACY_ERROR


def test_canonicalize_reason_code_strict_rejects_unknown_lirix_reason() -> None:
    code = lirix_constants.canonicalize_reason_code(
        "LIRIX_REASON_NOT_A_REAL_REASON",
        strict=True,
    )
    assert code == "LIRIX_REASON_UNKNOWN"


def test_resolve_failure_protocol_prefers_nested_context_reason() -> None:
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L4",
            "failure_type": "unknown",
            "retryable": False,
            "repair_hint": "hint",
            "details": {
                "context": {"reason": "timeout"},
                "error_code": "LRX_L4_CONSENSUS_FAILED",
            },
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_TIMEOUT"


def test_resolve_failure_protocol_uses_canonical_reason_code_field() -> None:
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L4",
            "failure_type": "junk",
            "retryable": False,
            "details": {"canonical_reason_code": "policy_violation"},
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_POLICY_VIOLATION"


def test_resolve_failure_protocol_falls_back_to_top_level_failure_type() -> None:
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L4",
            "failure_type": "transport_error",
            "retryable": True,
            "repair_hint": "r",
            "details": {},
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_TRANSPORT_ERROR"


def test_resolve_failure_protocol_skips_empty_context_reason_strings() -> None:
    """Cover branch where context.reason is str but falsy after strip."""
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L2",
            "failure_type": "timeout",
            "retryable": True,
            "details": {"context": {"reason": ""}, "canonical_reason_code": ""},
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_TIMEOUT"


def test_resolve_failure_protocol_whitespace_only_tokens_skip_reason_extraction() -> None:
    """Whitespace-only context.reason / failure_type does not populate raw_reason."""
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L9",
            "failure_type_canonical": "timeout",
            "failure_type": "   ",
            "retryable": False,
            "details": {"context": {"reason": "  \t  "}},
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_UNKNOWN"


def test_resolve_nested_agent_feedback_unknown_failure_type_uses_inner_failure_type() -> None:
    out = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L4",
            "failure_type": "unknown",
            "details": {
                "agent_feedback": {
                    "schema_version": "1.0",
                    "failure_type": "schema_validation_failed",
                    "layer": "L2",
                    "reason_code": "LIRIX_REASON_SCHEMA_INVALID",
                    "retry_allowed": False,
                    "remediation": "fix",
                    "details": {},
                }
            },
        }
    )
    assert out["failure_type"] == "schema_validation_failed"


def test_verify_forensic_bundle_version_mismatch() -> None:
    b = dict(_minimal_forensic_bundle())
    b["forensic_version"] = "0.9"
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_version"


def test_verify_forensic_bundle_replay_version_mismatch() -> None:
    b = dict(_minimal_forensic_bundle())
    b["replay_bundle_version"] = "1.0"
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_replay_version"


def test_verify_forensic_bundle_matrix_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    b = dict(_minimal_forensic_bundle())
    monkeypatch.setattr(
        "lirix.core.forensic_verifier.ALLOWED_BUNDLE_VERSION_MATRIX",
        frozenset(),
    )
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_version_matrix"


def test_verify_forensic_bundle_bad_session_id() -> None:
    b = dict(_minimal_forensic_bundle())
    b["session_id"] = ""
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_malformed"


def test_verify_forensic_bundle_list_field_not_list() -> None:
    b = dict(_minimal_forensic_bundle())
    b["error_codes"] = "nope"
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_malformed"


def test_verify_forensic_bundle_rbd_must_be_string_when_not_enforcing() -> None:
    b = dict(_minimal_forensic_bundle())
    b["replay_bundle_digest"] = 123
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b, enforce_replay_link=False)
    assert exc.value.context.get("field") == "replay_bundle_digest"


def test_verify_forensic_bundle_registry_closure_digest_malformed() -> None:
    b = dict(_minimal_forensic_bundle())
    b["registry_closure_digest"] = "zz"
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(b)
    assert exc.value.context.get("reason") == "forensic_bundle_registry_closure_digest_malformed"


def test_verify_forensic_bundle_rejects_non_mapping_replay_bundle() -> None:
    b = dict(_minimal_forensic_bundle())
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(
            dict(b),
            enforce_replay_link=True,
            replay_bundle=cast(Any, "not-a-mapping"),
        )
    assert exc.value.context.get("reason") == "forensic_bundle_replay_bundle_malformed"


def test_verify_forensic_bundle_rejects_bad_replay_bundle_digest_under_enforcement() -> None:
    fb = dict(_minimal_forensic_bundle())
    fb["replay_bundle_digest"] = "not-a-hex-digest-at-all"
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(fb, enforce_replay_link=True)
    assert exc.value.context.get("reason") == "forensic_bundle_replay_digest_malformed"


def test_verify_forensic_bundle_rejects_malformed_nested_replay_bundle_digest() -> None:
    fb = dict(_minimal_forensic_bundle())
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(
            fb,
            enforce_replay_link=True,
            replay_bundle={"bundle_digest": "zzz"},
        )
    assert exc.value.context.get("reason") == "forensic_bundle_replay_bundle_digest_malformed"


def test_verify_forensic_bundle_rejects_bad_nested_bundle_digest() -> None:
    b = dict(_minimal_forensic_bundle())
    fb = dict(b)
    fb["replay_bundle_digest"] = "b" * 64
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_forensic_bundle(
            fb,
            enforce_replay_link=True,
            replay_bundle={
                "bundle_digest": "c" * 64,
                "bundle_version": REPLAY_BUNDLE_VERSION,
            },
        )
    assert exc.value.context.get("reason") == "forensic_replay_bundle_digest_mismatch"


def test_lirix_replay_from_bundle_strict_branch_calls_verify() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "x",
            "steps": [],
        },
        status="ok",
        replay_proof={
            "chain_registry_digest": "a" * 64,
            "decoder_registry_digest": "b" * 64,
            "registry_version": "v1",
            "registry_source": "test",
        },
    )
    s.record_plan(objective="o", constraints=[])
    s.record_draft(label="d", content={})
    s.record_decision(verdict="approved", rationale="ok")
    s.finalize(outcome="ok")
    rb = s.replay_bundle()
    Lirix.replay_from_bundle(rb, enforce_replay_proof_strict=True)


def test_lirix_raises_when_hook_trace_recorder_missing_direct_call() -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])
    with pytest.raises(ConfigurationGuardException) as exc:
        guard._ensure_hook_trace_binding()
    assert exc.value.context.get("reason") == "hook_trace_recorder_missing"


def test_lirix_strict_mode_registry_address_requires_allowlist() -> None:
    """Use an address Web3 reliably classifies so the strict-mode allowlist gate is exercised."""
    with pytest.raises(ConfigurationGuardException) as exc:
        Lirix(
            rpc_urls=["https://example.invalid"],
            runtime_patch={
                "strict_mode": True,
                "chain_profile": {
                    "protocol_registry": {
                        "lbl": "0xdac17f958d2ee523a2206206994597c13d831ec7",
                    },
                },
            },
        )
    assert exc.value.context.get("reason") == "registry_allowlist_required"


def test_lirix_strict_mode_registry_non_address_values_skip_allowlist_gate() -> None:
    """Empty allowlist only blocks when registry values look like Ethereum addresses."""
    Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "strict_mode": True,
            "chain_profile": {
                "protocol_registry": {"lbl": "not-an-ethereum-address-token"},
            },
        },
    )


class _BareDecoderPlug:
    name = "zp_cov_decoder"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return False

    def decode_and_collect(self, **_kwargs: object) -> dict[str, Any]:
        return {}


def test_lirix_decoder_mode_profile_allowlist_and_named_decoder_resolution() -> None:
    plug = _BareDecoderPlug()
    guard = Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "decoder_plugins": [plug],
            "chain_profile": {"decoder_plugins": [_BareDecoderPlug.name]},
            "chain_id": 1,
        },
    )
    assert guard._decoder_mode() == "profile_allowlist"
    assert _BareDecoderPlug.name in guard._resolved_decoder_plugins()


def test_lirix_resolved_decoder_plugins_skips_bad_name_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])

    class _NoName:
        pass

    monkeypatch.setattr(
        guard.chain_adapter,
        "decoder_plugins",
        lambda: [_NoName()],
    )
    assert guard._resolved_decoder_plugins() == []
    guard._decoder_mode()


def test_l4_disagreement_entry_maps_unknown_rpc_reason_via_unknown_taxon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lirix.layers.l4_rpc_manager.canonical_reason_from_rpc_reason",
        lambda _: None,
    )
    cfg = LirixConfig(rpc_urls=["https://x.invalid"], chain_id=1)
    mgr = RPCManager(cfg, hooks=HookManager())
    rep = mgr._build_disagreement_report(reason="r", classified={}, heights={})
    for _k, blob in rep.taxonomy.items():
        assert blob["canonical_reason_code"] == "LIRIX_REASON_UNKNOWN"


def test_hook_patch_non_payload_target_warn_mode_emits_SHADOW_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    mgr = HookManager(contract_mode="shadow")

    def cb(*_: object, **__: object) -> HookPatch:
        return HookPatch(updates={}, target="intent", reason="x")

    from lirix.core.constants import HOOK_PRE_VALIDATE

    mgr.register_hook(HOOK_PRE_VALIDATE, cb)
    out = mgr.invoke_hooks_isolated(
        HOOK_PRE_VALIDATE,
        intent="swap",
        payload={"to": "0x1"},
    )
    assert out and out[0].get("ok") is True
    assert out[0].get("error_code") == HOOK_WARN_PATCH_TARGET_SHADOW


def test_session_fsm_ignores_untracked_event_types_when_collecting_seen() -> None:
    fsm = SessionFSM()
    timeline = [
        {"kind": "session_event", "event_type": "plan"},
        {"kind": "session_event", "event_type": "bookmark"},
    ]
    fsm.validate_append(
        lifecycle="running",
        timeline=timeline,
        incoming=SessionEvent(kind="session_event", event_type="draft"),
        workflow_strict=True,
    )


def test_session_fsm_skips_non_mapping_timeline_items() -> None:
    fsm = SessionFSM()
    timeline = [
        {"kind": "session_event", "event_type": "plan"},
        "not-a-mapping",
    ]
    fsm.validate_append(
        lifecycle="running",
        timeline=timeline,
        incoming=SessionEvent(kind="session_event", event_type="draft"),
        workflow_strict=True,
    )


def test_verify_replay_bundle_ignores_decision_count_when_not_int() -> None:
    """decision_count cross-check runs only for int; other types are skipped (digest unchanged)."""
    s = ValidationSession()
    rb = dict(s.replay_bundle())
    rb["decision_count"] = "not-an-int"
    verify_replay_bundle(rb)


def test_verify_replay_bundle_decision_count_mismatch_from_minimal_bundle() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "replay_proof": {},
        "timeline_size": 0,
        "decision_count": 2,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_decision_count_mismatch"


def test_verify_replay_bundle_last_trace_digest_malformed() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": "bad",
        "artifact_digests": {},
        "replay_proof": {},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_last_trace_digest_malformed"


def test_verify_replay_bundle_artifact_key_empty_string() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {"": "f" * 64},
        "replay_proof": {},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_artifact_digests_malformed"


def test_verify_replay_bundle_replay_proof_not_mapping() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "replay_proof": [1, 2],
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_replay_proof_malformed"


def test_verify_replay_bundle_integrity_raises_on_bundle_digest_mismatch() -> None:
    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "z", "steps": []},
        status="ok",
    )
    rb = s.replay_bundle()
    bad = dict(rb)
    bad["bundle_digest"] = "e" * 64
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(bad)
    assert exc.value.context.get("reason") == "replay_bundle_integrity"


def test_verify_replay_bundle_artifact_digest_values_must_be_hex() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {"ext_x": "not-a-digest"},
        "replay_proof": {},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_artifact_digests_malformed"


def test_validation_session_registry_closure_digest_drift_raises() -> None:
    sess = ValidationSession()
    sess.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "t1",
            "steps": [],
        },
        status="ok",
        registry_closure_digest="a" * 64,
    )
    sess.record_trace(
        kind="validate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "t2",
            "steps": [],
        },
        status="ok",
        registry_closure_digest="b" * 64,
    )
    with pytest.raises(ConfigurationGuardException) as exc:
        sess.replay_bundle()
    assert exc.value.context.get("reason") == "replay_bundle_metadata_drift"


def test_verify_replay_bundle_decoder_digest_malformed() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "replay_proof": {"decoder_registry_digest": "x"},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_replay_proof_malformed"


def test_verify_replay_bundle_registry_source_not_string() -> None:
    payload = {
        "session_id": "s",
        "created_at": "t",
        "correlation_ids": [],
        "timeline": [],
        "state": {},
    }
    b: dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "bundle_digest": "0" * 64,
        "migration_modes": {},
        "config_fingerprint": None,
        "last_trace_digest": None,
        "artifact_digests": {},
        "replay_proof": {"registry_source": 1},
        "timeline_size": 0,
        "decision_count": 0,
        "payload": payload,
    }
    with pytest.raises(ConfigurationGuardException) as exc:
        verify_replay_bundle(b)
    assert exc.value.context.get("reason") == "replay_bundle_replay_proof_malformed"
    assert exc.value.context.get("key") == "registry_source"


@pytest.mark.asyncio
async def test_langchain_tool_ainvoke_validate_only_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    async def _fake_async_validate_only(
        self: Any,
        intent: str,
        payload: Mapping[str, Any],
    ) -> dict[str, str]:
        return {"intent": intent, "mode": "validate_only"}

    monkeypatch.setattr(Lirix, "async_validate_only", _fake_async_validate_only)

    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = await tool._ainvoke_guardian(
        "raw",
        intent="swap",
        mode="validate_only",
    )
    assert "validate_only" in out


def test_lirix_raise_with_failure_context_when_agent_feedback_is_mapping_but_not_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    sess = ValidationSession()

    mf: Mapping[str, Any] = MappingProxyType(
        {
            "schema_version": "1.0",
            "failure_type": "timeout",
            "layer": "L1",
            "reason_code": "",
            "retry_allowed": True,
            "remediation": "r",
            "details": MappingProxyType({}),
        }
    )

    monkeypatch.setattr("lirix.core.orchestrator.rejected_step_to_agent_feedback", lambda *_a, **_k: mf)
    trace = SecurityTrace.new(correlation_id="c", intent="swap", payload={"to": "0x1"})
    from lirix.core.exceptions import LirixSecurityException
    from lirix.core.orchestrator import LirixPipelineOrchestrator
    from lirix.core.trace_recorder import TraceRecorder

    exc = LirixSecurityException(
        human_readable_reason="bad",
        error_code="E",
        context={
            "layer": "L1",
            "reason": "intent",
            "correlation_id": "c",
        },
        value_protected="vp",
    )
    recorder = TraceRecorder(trace=trace)
    with pytest.raises(LirixSecurityException):
        LirixPipelineOrchestrator._record_failure(
            guard,
            sess=sess,
            kind="validate_only",
            trace=trace,
            intent="swap",
            correlation_id="c",
            exc=exc,
            manage_session_lifecycle=False,
            blocked_note="n",
            recorder=recorder,
        )
