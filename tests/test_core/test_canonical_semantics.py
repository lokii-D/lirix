from __future__ import annotations

from lirix.core.canonical_taxonomy import lookup_reason_taxon
from lirix.core.constants import (
    AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    AGENT_FEEDBACK_REASON_TIMEOUT,
    FAILURE_TYPE_CONSENSUS_FAILURE,
    FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
    FAILURE_TYPE_TIMEOUT,
    canonicalize_error_code,
    canonicalize_failure_type,
    canonicalize_reason_code,
    is_known_reason_code,
)
from lirix.core.evidence import SecurityTrace, rejected_step_to_agent_feedback
from lirix.core.exceptions import LirixBaseException
from lirix.core.failure_protocol import (
    build_failure_protocol_from_agent_feedback,
    resolve_failure_protocol_to_agent_feedback,
)


def test_canonical_reason_and_failure_type_mappings() -> None:
    assert canonicalize_reason_code("timeout") == AGENT_FEEDBACK_REASON_TIMEOUT
    assert canonicalize_reason_code("", fallback_error_code="LRX_L4_CONSENSUS_FAILED") == (
        AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE
    )
    assert canonicalize_failure_type("timeout") == FAILURE_TYPE_TIMEOUT
    assert canonicalize_failure_type("", fallback_reason_code="LIRIX_REASON_CONSENSUS_FAILURE") == (
        FAILURE_TYPE_CONSENSUS_FAILURE
    )
    assert canonicalize_reason_code("reconcile_failed") == "LIRIX_REASON_RECONCILE_PARTIAL_FAILURE"
    assert canonicalize_reason_code("height_spread_exceeded") == "LIRIX_REASON_CONSENSUS_FAILURE"
    assert canonicalize_reason_code("hook_blocked") == "LIRIX_REASON_POLICY_VIOLATION"
    assert canonicalize_failure_type("rpc_error") == "transport_error"


def test_canonical_taxonomy_lookup_is_authoritative() -> None:
    timeout = lookup_reason_taxon("LIRIX_REASON_TIMEOUT")
    assert timeout.reason_code == "LIRIX_REASON_TIMEOUT"
    assert timeout.retry_allowed is True
    assert timeout.human_action_required is False
    unknown = lookup_reason_taxon("LIRIX_REASON_NOT_DEFINED")
    assert unknown.reason_code == "LIRIX_REASON_UNKNOWN"


def test_exception_to_dict_contains_canonical_error_code() -> None:
    exc = LirixBaseException(error_code="LRX_L4_CONSENSUS_FAILED")
    data = exc.to_dict()
    assert data["error_code"] == "LRX_L4_CONSENSUS_FAILED"
    assert data["canonical_error_code"] == canonicalize_error_code("LRX_L4_CONSENSUS_FAILED")


def test_failure_protocol_roundtrip_prefers_canonical_fields() -> None:
    af = {
        "schema_version": "1.0",
        "failure_type": "security_rejection",
        "layer": "L4",
        "reason_code": "LIRIX_REASON_TIMEOUT",
        "retry_allowed": True,
        "remediation": "retry later",
        "details": {},
    }
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L4",
        failure_type="reconcile_partial_failure",
        agent_feedback=af,
        details={"context": {"reason": "timeout"}},
    )
    assert fp["failure_type_canonical"] == FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE
    back = resolve_failure_protocol_to_agent_feedback(fp)
    assert back["reason_code"] == AGENT_FEEDBACK_REASON_TIMEOUT


def test_failure_protocol_nested_agent_feedback_is_canonicalized_on_resolve() -> None:
    fp = {
        "schema_version": "1.0",
        "failure_layer": "L4",
        "failure_type": "unknown",
        "failure_type_canonical": "unknown",
        "retryable": False,
        "repair_hint": "blocked",
        "human_action_required": True,
        "details": {
            "agent_feedback": {
                "schema_version": "1.0",
                "failure_type": "rpc_error",
                "layer": "L4",
                "reason_code": "timeout",
                "retry_allowed": True,
                "remediation": "retry",
                "details": {"error_code": "LRX_L4_CONSENSUS_FAILED"},
            }
        },
    }
    out = resolve_failure_protocol_to_agent_feedback(fp)
    assert out["reason_code"] == "LIRIX_REASON_TIMEOUT"
    assert out["failure_type"] == "timeout"


def test_failure_protocol_reason_fallback_prefers_details_error_code() -> None:
    af = {
        "schema_version": "1.0",
        "failure_type": "security_rejection",
        "layer": "L4",
        "reason_code": "",
        "retry_allowed": False,
        "remediation": "blocked",
        "details": {"error_code": "LRX_L4_CONSENSUS_FAILED"},
    }
    fp = build_failure_protocol_from_agent_feedback(
        failure_layer="L4",
        failure_type="unknown",
        agent_feedback=af,
        details={"error_code": "LRX_L4_CONSENSUS_FAILED"},
    )
    assert fp["details"]["canonical_reason_code"] == AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE


def test_rejected_step_agent_feedback_failure_type_follows_reason() -> None:
    trace = SecurityTrace.new(correlation_id="c1", intent="swap", payload={"to": "0x1"})
    exc = LirixBaseException(
        error_code="LRX_LEGACY_ERROR", context={"layer": "L1", "reason": "timeout"}
    )
    af = rejected_step_to_agent_feedback(
        trace,
        intent="swap",
        correlation_id="c1",
        exc=exc,
        failure_context={"layer": "L1", "reason": "timeout"},
    )
    assert af["reason_code"] == AGENT_FEEDBACK_REASON_TIMEOUT
    assert af["failure_type"] == FAILURE_TYPE_TIMEOUT


def test_canonicalize_reason_code_strict_rejects_unknown_prefixed_value() -> None:
    assert canonicalize_reason_code("LIRIX_REASON_CUSTOM", strict=True) == "LIRIX_REASON_UNKNOWN"
    assert is_known_reason_code("LIRIX_REASON_TIMEOUT") is True
    assert is_known_reason_code("LIRIX_REASON_CUSTOM") is False


def test_canonicalize_error_code_strict_rejects_unknown_tokens() -> None:
    assert canonicalize_error_code("LRX_NOT_MAPPED", strict=False) == "LRX_NOT_MAPPED"
    assert canonicalize_error_code("LRX_NOT_MAPPED", strict=True) == "LIRIX_ERR_LEGACY_ERROR"


def test_broadcast_payload_invariant_canonical_error_code_is_registered() -> None:
    assert (
        canonicalize_error_code("LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT", strict=True)
        == "LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT"
    )


def test_legacy_error_codes_emitted_by_runtime_are_canonicalized() -> None:
    legacy_codes = {
        "LRX_L4_CONSENSUS_FAILED",
        "LRX_RPC_QUORUM_FAILED",
        "LRX_SHADOW_POLICY_BLOCKED",
        "LRX_SIM_ASYNC_PAYLOAD",
        "LRX_TIMEOUT_BLOCK",
        "LRX_SIM_TARGET_REQUIRED",
        "LRX_SIM_ARGS_TYPE",
        "LRX_SIM_SIGNATURE_REQUIRED",
        "LRX_BRIDGE_PROTOCOL_UNSUPPORTED",
        "LRX_BRIDGE_ROUTE_UNSUPPORTED",
        "LRX_INTENT_TYPE_UNSUPPORTED",
        "LRX_INTENT_MISSING_FIELDS",
        "LRX_BRIDGE_SIGNATURE_UNSUPPORTED",
        "LRX_ASSERTION_CONFIG_INVALID",
        "LRX_HONEYPOT_DETECTED",
        "LRX_STATE_MISMATCH",
        "LRX_DEP_SIMULATION_MISSING",
        "LRX_SIM_CONTRACT_LOGIC",
        "LRX_SIM_WEB3_ERROR",
        "LRX_SIM_VALUE_ERROR",
        "LRX_VALIDATION_ARG_COUNT",
        "LRX_VALIDATION_ABI_ENCODE",
        "LRX_HALLUCINATION_ADDRESS",
        "LRX_VALIDATION_NUMERIC_TYPE",
        "LRX_VALIDATION_SIGNATURE_EMPTY",
        "LRX_VALIDATION_SIGNATURE_FORMAT",
    }
    for code in legacy_codes:
        assert canonicalize_error_code(code).startswith("LIRIX_ERR_")


def test_rejected_step_retry_allowed_follows_canonical_failure_type() -> None:
    trace = SecurityTrace.new(correlation_id="c2", intent="swap", payload={"to": "0x1"})
    exc = LirixBaseException(
        error_code="LRX_LEGACY_ERROR", context={"layer": "L4", "reason": "reconcile_failed"}
    )
    af = rejected_step_to_agent_feedback(
        trace,
        intent="swap",
        correlation_id="c2",
        exc=exc,
        failure_context={"layer": "L4", "reason": "reconcile_failed"},
    )
    assert af["reason_code"] == "LIRIX_REASON_RECONCILE_PARTIAL_FAILURE"
    assert af["failure_type"] == FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE
    assert af["retry_allowed"] is True
