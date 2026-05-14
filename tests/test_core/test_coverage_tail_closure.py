# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Targeted branch coverage for pyproject fail_under=100 on lirix/."""

from __future__ import annotations

import copy
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, cast
from unittest.mock import MagicMock

import pytest
from lirix import Lirix
from lirix.core import constants as lirix_constants
from lirix.core.canonical_taxonomy import (
    canonical_reason_from_rpc_reason,
    lookup_reason_taxon,
)
from lirix.core.client_components import pipeline_orchestrator, request_normalization
from lirix.core.config import LirixConfig
from lirix.core.constants import (
    AGENT_FEEDBACK_REASON_OK,
    AGENT_FEEDBACK_SCHEMA_VERSION,
    HOOK_LAYER_L5,
    HOOK_PRE_VALIDATE,
    HOOK_WARN_PATCH_TARGET_SHADOW,
    LIRIX_ERR_LEGACY_ERROR,
    LIRIX_ERR_POLICY_BLOCKED,
)
from lirix.core.evidence import (
    AgentFeedbackEnvelope,
    PolicyDecision,
    QuorumVerdict,
    SecurityTrace,
    build_agent_feedback_success,
)
from lirix.core.exceptions import (
    ConfigurationGuardException,
    LirixPolicyViolationException,
    LirixSecurityException,
    MaliciousPayloadException,
)
from lirix.core.failure_protocol import (
    build_failure_protocol,
    resolve_failure_protocol_to_agent_feedback,
)
from lirix.core.forensic_verifier import verify_forensic_bundle
from lirix.core.hook_contract import HookDecision, HookPatch
from lirix.core.hook_manager import HookManager
from lirix.core.registry_authority import assert_registry_authority_contract
from lirix.core.session import (
    FORENSIC_BUNDLE_VERSION,
    REPLAY_BUNDLE_VERSION,
    ValidationSession,
    verify_replay_bundle,
)
from lirix.core.session_fsm import SessionEvent, SessionFSM
from lirix.integrations.autogen.tool import alirix_validate_intent, lirix_validate_intent
from lirix.integrations.langchain.tool import (
    LirixSecurityValidator,
    _format_security_exception,
    _merge_raw_intent_overlay,
    _serialize_guardian_success,
)
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from lirix.layers.l3_proxy_piercer import AbiLRUCache
from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_sandbox_simulator import SandboxSimulator


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
    s = ValidationSession(workflow_mode="direct")
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
    s = ValidationSession(workflow_mode="direct")
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
        "workflow_mode": "direct",
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
        "workflow_mode": "direct",
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
        "workflow_mode": "direct",
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
        "workflow_mode": "direct",
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
    s = ValidationSession(workflow_mode="direct")
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
        "workflow_mode": "direct",
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
    sess = ValidationSession(workflow_mode="direct")
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
        "workflow_mode": "direct",
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
        "workflow_mode": "direct",
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
        **kwargs: Any,
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
    sess = ValidationSession(workflow_mode="direct")

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

    monkeypatch.setattr(
        "lirix.core.orchestrator.rejected_step_to_agent_feedback", lambda *_a, **_k: mf
    )
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


def test_lirix_main_module_import_exposes_cli_entrypoint() -> None:
    import lirix.__main__ as lirix_main

    assert callable(lirix_main.main)


def test_lirix_main_exec_invokes_cli_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import lirix.cli as cli_mod

    called: dict[str, bool] = {}

    def fake_main() -> None:
        called["ok"] = True

    monkeypatch.setattr(cli_mod, "main", fake_main)
    p = Path(__file__).resolve().parents[2] / "lirix" / "__main__.py"
    ns: dict[str, Any] = {"__name__": "__main__", "__builtins__": __builtins__}
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), ns)
    assert called.get("ok") is True


def test_multicall_resolve_mainnet_default_address() -> None:
    from lirix._multicall_facade import _resolve_multicall3_address

    class _Cfg:
        multicall3_address = ""
        chain_id = 1

    addr = _resolve_multicall3_address(_Cfg())
    assert addr.startswith("0x")


def test_request_normalization_deepcopy_error_raises_configuration_guard() -> None:
    class _NoCopy:
        def __deepcopy__(self, memo: dict[int, Any]) -> Any:
            raise copy.Error("not copyable")

    sess = ValidationSession(workflow_mode="direct")
    with pytest.raises(ConfigurationGuardException) as exc:
        request_normalization(
            session=sess,
            manage_session_lifecycle=False,
            correlation_id="c1",
            intent="swap",
            payload={"x": _NoCopy()},
        )
    assert exc.value.context.get("reason") == "payload_deepcopy_failed"


def test_pipeline_orchestrator_dict_wrapper() -> None:
    out = pipeline_orchestrator(
        chain_context={"a": 1},
        runtime_semantics={"b": 2},
        quorum_verdict={"c": 3},
    )
    assert out == {
        "chain_context": {"a": 1},
        "runtime_semantics": {"b": 2},
        "quorum_verdict": {"c": 3},
    }


def test_canonicalize_failure_type_uses_reason_fallback_mapping() -> None:
    ft = lirix_constants.canonicalize_failure_type(
        "not_a_known_failure_token_xyz",
        fallback_reason_code="LIRIX_REASON_TIMEOUT",
    )
    assert ft == lirix_constants.FAILURE_TYPE_TIMEOUT


def test_evidence_datatypes_to_dict_and_success_builder() -> None:
    qd = QuorumVerdict(
        block_number=1,
        selected_rpc_url="http://x",
        quorum_ok=False,
        required_votes=None,
        observed_votes=3,
        details={},
    ).to_dict()
    assert "required_votes" not in qd and qd["observed_votes"] == 3

    pd = PolicyDecision(
        policy_id="p",
        policy_version="1",
        environment="e",
        verdict="v",
        details={"k": 1},
    ).to_dict()
    assert pd["policy_id"] == "p"

    af = AgentFeedbackEnvelope(
        failure_type="t",
        layer="L1",
        reason_code="LIRIX_REASON_OK",
        retry_allowed=False,
        remediation="r",
        details={},
    ).to_dict()
    assert af["schema_version"] == AGENT_FEEDBACK_SCHEMA_VERSION

    ok_fb = build_agent_feedback_success(stage="s", intent="i", correlation_id="c")
    assert ok_fb["reason_code"] == AGENT_FEEDBACK_REASON_OK


def test_build_failure_protocol_wrapper() -> None:
    fp = build_failure_protocol(
        failure_layer="L1",
        failure_type="timeout",
        retryable=False,
        repair_hint="h",
        human_action_required=True,
        details={"k": 1},
    )
    assert fp["failure_layer"] == "L1"
    assert fp["details"] == {"k": 1}


def test_registry_authority_contract_rejects_missing_required_field() -> None:
    bad = {
        "schema_version": "1.0",
        "authority_source": "x",
        "chain_registry_authority": "a",
        "decoder_registry_authority": "b",
        "chain_registry_keys": [],
        "decoder_registry_keys": [],
        "authority_digest": "0" * 64,
    }
    del bad["decoder_registry_keys"]
    with pytest.raises(ConfigurationGuardException) as exc:
        assert_registry_authority_contract(bad)
    assert exc.value.context.get("reason") == "registry_authority_missing_fields"


def test_strict_registry_skips_non_string_protocol_values() -> None:
    Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "strict_mode": True,
            "chain_profile": {"protocol_registry": {"lbl": 12345}},
        },
    )


@pytest.mark.asyncio
async def test_hook_manager_ainvoke_mixed_async_sync_with_positive_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    mgr = HookManager(contract_mode="enforce")

    async def async_ok(*_a: object, **_k: object) -> HookDecision:
        return HookDecision(status="approved")

    def sync_ok(*_a: object, **_k: object) -> HookDecision:
        return HookDecision(status="approved")

    mgr.register_hook(HOOK_PRE_VALIDATE, async_ok)
    mgr.register_hook(HOOK_PRE_VALIDATE, sync_ok)
    out = await mgr.ainvoke_hooks_isolated(
        HOOK_PRE_VALIDATE,
        intent="swap",
        payload={"to": "0x1"},
        timeout_sec=0.5,
    )
    assert len(out) == 2 and all(x.get("ok") for x in out)


@pytest.mark.asyncio
async def test_lirix_run_coroutine_sync_propagates_lirix_security_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    g = Lirix(rpc_urls=["https://example.invalid"])

    async def boom() -> dict[str, Any]:
        raise LirixSecurityException(
            human_readable_reason="boom",
            error_code="E_TEST_COVERAGE",
            context={"layer": "L1"},
        )

    with pytest.raises(LirixSecurityException):
        g._run_coroutine_sync(lambda: boom())


@pytest.mark.asyncio
async def test_lirix_run_coroutine_sync_thread_pool_propagates_plain_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a running loop, _run_coroutine_sync uses a thread pool; non-Lirix errors
    traverse the cause/context unwind and re-raise the outer exception (lirix/_facade).
    """
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    g = Lirix(rpc_urls=["https://example.invalid"])

    async def boom() -> dict[str, Any]:
        raise ValueError("plain_sync_thread_pool")

    with pytest.raises(ValueError, match="plain_sync_thread_pool"):
        g._run_coroutine_sync(lambda: boom())


def _exception_chain_depth(depth: int) -> BaseException:
    """Build ``depth`` linked exceptions via __cause__ (deepest is ValueError)."""
    cur: BaseException = ValueError("leaf")
    for i in range(depth - 1):
        nxt = RuntimeError(f"wrap_{i}")
        nxt.__cause__ = cur
        cur = nxt
    return cur


@pytest.mark.asyncio
async def test_lirix_run_coroutine_sync_thread_pool_deep_chain_reraises_outer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unwind stops after 24 hops; if no LirixBaseException is found, the original outer
    exception is re-raised (covers for-loop exhaustion path in _run_coroutine_sync).
    """
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    g = Lirix(rpc_urls=["https://example.invalid"])
    deep = _exception_chain_depth(30)

    async def boom() -> dict[str, Any]:
        raise deep

    with pytest.raises(RuntimeError, match="wrap_28"):
        g._run_coroutine_sync(lambda: boom())


def test_lirix_resolve_failure_protocol_non_mapping_nested_uses_outer_context() -> None:
    inner = resolve_failure_protocol_to_agent_feedback(
        {
            "schema_version": "1.0",
            "failure_layer": "L1",
            "failure_type": "timeout",
            "retryable": False,
            "repair_hint": "h",
            "human_action_required": False,
            "details": {},
        }
    )
    outer = dict(inner)
    outer["failure_protocol"] = "not-a-mapping"
    out = Lirix.resolve_failure_protocol(outer)
    assert isinstance(out, dict) and out.get("reason_code")


def test_extract_broadcast_fields_bool_coercion_on_approved_path() -> None:
    out = Lirix.extract_broadcast_fields(
        {
            "decision": "approved",
            "status": "approved",
            "payload": {
                "to": "0x4200000000000000000000000000000000000006",
                "data": "0x",
                "value": True,
            },
        }
    )
    assert out["value"] == 1


def test_extract_broadcast_fields_approved_missing_data_raises() -> None:
    with pytest.raises(LirixSecurityException) as excinfo:
        Lirix.extract_broadcast_fields(
            {
                "decision": "approved",
                "status": "approved",
                "payload": {
                    "to": "0x4200000000000000000000000000000000000006",
                    "data": "",
                    "value": 0,
                },
            }
        )
    assert excinfo.value.context.get("reason") == "approved_broadcast_fields_invariant"


def test_lirix_decoder_mode_explicit_when_decoder_plugin_list_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    g = Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "chain_profile": {"decoder_plugins": [], "decoder_policy": "explicit_only"},
        },
    )
    assert g._decoder_mode() == "explicit_only"


def test_defi_parser_resolves_multicall_router_via_chain_adapter_on_non_mainnet() -> None:
    class _CA:
        def decoder_plugins(self) -> list[object]:
            return []

        def resolve_l3_targets(self) -> dict[str, str]:
            return {
                "multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11",
                "uniswap_v2_router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            }

    cfg = LirixConfig(
        chain_id=42161,
        strict_mode=False,
        rpc_urls=[],
        multicall3_address=None,
        uniswap_v2_router=None,
    )
    p = DeFiPayloadParser(cfg, chain_adapter=_CA())
    assert p._multicall().startswith("0x")
    assert p._router().startswith("0x")


def test_abi_lru_cache_copy_cached_abi_falls_back_when_deepcopy_fails() -> None:
    class _Bad:
        def __deepcopy__(self, memo: dict[int, Any]) -> Any:
            raise copy.Error("x")

    bad = _Bad()
    assert AbiLRUCache._copy_cached_abi(bad) is bad


def test_sandbox_simulator_invokes_l5_hooks_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    hooks = HookManager(contract_mode="enforce")

    def on_l5(*_a: object, **_k: object) -> HookDecision:
        return HookDecision(status="approved")

    hooks.register_hook(HOOK_LAYER_L5, on_l5)
    w3 = MagicMock()
    w3.eth.call.return_value = b"\x00" * 32
    sim = SandboxSimulator(hooks=hooks, backend_profile={})
    out = sim.simulate(
        {"to": "0x4200000000000000000000000000000000000006", "data": "0x", "value": 0},
        web3=w3,
        block_number=1,
    )
    assert isinstance(out, dict)


def test_autogen_lirix_validate_intent_returns_feedback_on_json_merge_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _G:
        def validate_and_simulate(self, *_a: object, **_k: object) -> dict[str, Any]:
            return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.integrations.autogen.tool.Lirix", lambda *_a, **_k: _G())
    out = lirix_validate_intent('{"a":}', ["https://example.invalid"], intent="swap")
    assert out.startswith("ACTION REQUIRED:")


@pytest.mark.asyncio
async def test_autogen_async_validate_intent_delegates_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lirix.integrations.autogen.tool.lirix_validate_intent",
        lambda *_a, **_k: '{"ok": true}',
    )
    got = await alirix_validate_intent("{}", ["https://example.invalid"], intent="swap")
    assert got == '{"ok": true}'


def test_langchain_merge_overlay_json_object_non_dict_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as _json

    def _loads(s: str, *_a: object, **_k: object) -> Any:
        if s.strip() == '{"x": true}':
            return [1, 2]
        return _json.loads(s)

    monkeypatch.setattr("lirix.integrations.langchain.tool.json.loads", _loads)
    raw = '{"x": true}'
    out = _merge_raw_intent_overlay(raw_intent_or_calldata=raw, overlay={})
    assert out["raw_intent_or_calldata"] == raw and "x" not in out


def test_langchain_serialize_model_dump_non_mapping() -> None:
    class _M:
        def model_dump(self, mode: str = "python") -> object:
            return ["not", "mapping"]

    assert _serialize_guardian_success(_M()) == '["not", "mapping"]'


def test_langchain_serialize_model_dump_mapping_injects_tx_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )

    class _M:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"decision": "approved", "status": "approved", "payload": {}}

    text = _serialize_guardian_success(_M())
    assert "tx_payload" in text


def test_langchain_serialize_model_dump_json_invalid_returns_raw() -> None:
    class _M:
        def model_dump_json(self) -> str:
            return "NOT_JSON{{"

    assert _serialize_guardian_success(_M()) == "NOT_JSON{{"


def test_langchain_serialize_model_dump_json_list_returns_raw() -> None:
    class _M:
        def model_dump_json(self) -> str:
            return "[1, 2]"

    assert _serialize_guardian_success(_M()) == "[1, 2]"


def test_langchain_serialize_model_dump_json_object_adds_tx_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )

    class _M:
        def model_dump_json(self) -> str:
            return '{"decision": "approved", "status": "approved", "payload": {}}'

    text = _serialize_guardian_success(_M())
    assert "tx_payload" in text


def test_langchain_format_security_exception_reason_and_repair_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.resolve_failure_protocol",
        lambda _ctx: {
            "remediation": "BASE_REMED",
            "reason_code": "LIRIX_REASON_TIMEOUT",
        },
    )
    exc = LirixSecurityException(
        human_readable_reason="HUMAN_DETAIL_NOT_EQUAL_BASE",
        resolution_agent="fallback",
        context={
            "failure_protocol": {
                "schema_version": "1.0",
                "failure_layer": "L1",
                "failure_type": "t",
                "retryable": False,
                "repair_hint": "UNIQUE_REPAIR_STEP",
                "human_action_required": False,
                "details": {},
            }
        },
    )
    text = _format_security_exception(exc)
    assert "Reject detail:" in text
    assert "Reason code:" in text
    assert "Next step:" in text
    assert "UNIQUE_REPAIR_STEP" in text


def test_langchain_policy_blocked_branch_uses_canonical_policy_code() -> None:
    exc = LirixPolicyViolationException(
        error_code=LIRIX_ERR_POLICY_BLOCKED,
        resolution_agent="stop",
        context={"policy_key": "k", "expected": 1, "observed": 2},
    )
    text = _format_security_exception(exc)
    assert "Transaction Blocked by Lirix Policy" in text


def test_langchain_security_validator_validate_only_sync_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    def fake_validate_only(self: Any, intent: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
        return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.Lirix.validate_only", fake_validate_only)
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = tool._run("{}", mode="validate_only")
    assert "tx_payload" in out


@pytest.mark.asyncio
async def test_langchain_security_validator_ainvoke_guardian_validate_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    async def fake_async(self: Any, intent: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
        return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.Lirix.async_validate_only", fake_async)
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = await tool._ainvoke_guardian("{}", mode="validate_only")
    assert "tx_payload" in out


@pytest.mark.asyncio
async def test_langchain_security_validator_ainvoke_guardian_validate_and_simulate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    async def fake_async(self: Any, intent: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
        return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.Lirix.async_validate_and_simulate", fake_async)
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = await tool._ainvoke_guardian("{}", mode="validate_and_simulate")
    assert "tx_payload" in out


@pytest.mark.asyncio
async def test_langchain_security_validator_ainvoke_guardian_value_error_overlay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    async def fake_async(self: Any, intent: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
        return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.Lirix.async_validate_only", fake_async)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    # Braces on both ends force JSON parse attempt; invalid JSON raises ValueError in merge.
    out = await tool._ainvoke_guardian('{"bad-json":}', mode="validate_only")
    assert out.startswith("ACTION REQUIRED:")


@pytest.mark.asyncio
async def test_langchain_security_validator_ainvoke_guardian_merges_policies_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise _ainvoke_guardian merge paths (state_delta + security_policy) before merge."""
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    tool = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"],
        state_delta_assertions={"base_assert": 1},
        security_policy={"base_policy": True},
    )
    out = await tool._ainvoke_guardian(
        '{"trailing":}',
        mode="validate_only",
        state_delta_assertions={"call_assert": 2},
        security_policy={"call_policy": False},
    )
    assert out.startswith("ACTION REQUIRED:")


@pytest.mark.asyncio
async def test_langchain_security_validator_ainvoke_guardian_lirix_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)

    async def boom(self: Any, intent: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
        raise LirixSecurityException(
            human_readable_reason="blocked",
            error_code="E_TEST",
            context={"layer": "L1"},
        )

    monkeypatch.setattr("lirix.Lirix.async_validate_only", boom)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = await tool._ainvoke_guardian("{}", mode="validate_only")
    assert "blocked" in out


@pytest.mark.asyncio
async def test_lirix_run_coroutine_sync_unwraps_lirix_exception_via_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGCHAIN_SDK_MOCK_ONLY", raising=False)
    g = Lirix(rpc_urls=["https://example.invalid"])

    async def boom() -> dict[str, Any]:
        inner = LirixSecurityException(
            human_readable_reason="inner",
            error_code="E_INNER",
            context={"layer": "L1"},
        )
        raise RuntimeError("outer") from inner

    with pytest.raises(LirixSecurityException) as exc:
        g._run_coroutine_sync(lambda: boom())
    assert exc.value.error_code == "E_INNER"


def test_lirix_decoder_mode_explicit_when_decoder_plugins_not_a_list() -> None:
    # build_chain_profile normalizes decoder_plugins to a list of strings; a dict would
    # yield plugin names from keys. Use an empty dict so the adapter sees no plugins while
    # config.chain_profile still carries a non-list for _decoder_mode().
    g = Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "chain_profile": {
                "decoder_plugins": {},
                "decoder_policy": "explicit_only",
            },
        },
    )
    assert g._decoder_mode() == "explicit_only"


def test_defi_parser_multicall_raises_when_adapter_resolves_empty_string() -> None:
    class _CA:
        def decoder_plugins(self) -> list[object]:
            return []

        def resolve_l3_targets(self) -> dict[str, str]:
            return {
                "multicall3_address": "",
                "uniswap_v2_router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            }

    cfg = LirixConfig(chain_id=42161, strict_mode=False, rpc_urls=[], multicall3_address=None)
    p = DeFiPayloadParser(cfg, chain_adapter=_CA())
    with pytest.raises(MaliciousPayloadException):
        p._multicall()


def test_defi_parser_router_raises_when_adapter_resolves_empty_string() -> None:
    class _CA:
        def decoder_plugins(self) -> list[object]:
            return []

        def resolve_l3_targets(self) -> dict[str, str]:
            return {
                "multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11",
                "uniswap_v2_router": "",
            }

    cfg = LirixConfig(chain_id=42161, strict_mode=False, rpc_urls=[], uniswap_v2_router=None)
    p = DeFiPayloadParser(cfg, chain_adapter=_CA())
    with pytest.raises(MaliciousPayloadException):
        p._router()


def test_canonicalize_failure_type_unknown_reason_without_failure_type_mapping() -> None:
    ft = lirix_constants.canonicalize_failure_type(
        "unlisted_failure_type_token",
        fallback_reason_code="LIRIX_REASON_UNKNOWN",
    )
    assert ft == lirix_constants.FAILURE_TYPE_UNKNOWN


def test_canonicalize_failure_type_unknown_without_fallback_reason() -> None:
    """Covers canonicalize_failure_type when fallback_reason_code is omitted (branch to
    FAILURE_TYPE_UNKNOWN without using _REASON_TO_FAILURE_TYPE).
    """
    ft = lirix_constants.canonicalize_failure_type("unmapped_failure_type_token_xyz")
    assert ft == lirix_constants.FAILURE_TYPE_UNKNOWN


def test_quorum_verdict_to_dict_omits_default_none_vote_fields() -> None:
    d = QuorumVerdict(
        block_number=1,
        selected_rpc_url=None,
        quorum_ok=True,
        details={},
    ).to_dict()
    assert "required_votes" not in d and "observed_votes" not in d


def test_autogen_lirix_validate_intent_lirix_security_exception_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _G:
        def validate_and_simulate(self, *_a: object, **_k: object) -> dict[str, Any]:
            raise LirixSecurityException(
                human_readable_reason="blocked",
                error_code="E_TEST",
                context={"layer": "L1"},
            )

    monkeypatch.setattr("lirix.integrations.autogen.tool.Lirix", lambda *_a, **_k: _G())
    out = lirix_validate_intent("{}", ["https://example.invalid"], intent="swap")
    assert "blocked" in out


def test_autogen_lirix_validate_intent_success_serializes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _G:
        def validate_and_simulate(self, *_a: object, **_k: object) -> dict[str, Any]:
            return {"decision": "approved", "status": "approved", "payload": {}}

    monkeypatch.setattr("lirix.integrations.autogen.tool.Lirix", lambda *_a, **_k: _G())
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.extract_broadcast_fields",
        lambda _r: {"to": "0x1", "data": "0x", "value": 0},
    )
    out = lirix_validate_intent("{}", ["https://example.invalid"], intent="swap")
    assert "tx_payload" in out and "approved" in out


def test_langchain_format_security_exception_blank_repair_hint_skips_next_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fp = {
        "schema_version": "1.0",
        "failure_layer": "L1",
        "failure_type": "t",
        "retryable": False,
        "repair_hint": "   ",
        "human_action_required": False,
        "details": {},
    }
    monkeypatch.setattr(
        "lirix.integrations.langchain.tool.Lirix.resolve_failure_protocol",
        lambda _c: {"remediation": "REM_ONLY", "reason_code": ""},
    )
    exc = LirixSecurityException(
        human_readable_reason="REM_ONLY",
        resolution_agent="REM_ONLY",
        context={"failure_protocol": fp},
    )
    text = _format_security_exception(exc)
    assert "Next step:" not in text
