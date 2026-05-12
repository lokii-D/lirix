from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Dict, Mapping

from lirix.core.canonical_taxonomy import lookup_reason_taxon
from lirix.core.constants import (
    AGENT_FEEDBACK_REASON_OK,
    AGENT_FEEDBACK_SCHEMA_VERSION,
    canonicalize_failure_type,
    canonicalize_reason_code,
)

FAILURE_PROTOCOL_SCHEMA_VERSION: str = "1.0"


def stable_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def is_hex_digest(value: Any) -> bool:
    token = str(value or "").strip().lower()
    if len(token) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in token)


def build_agent_feedback_envelope(
    *,
    failure_type: str,
    layer: str,
    reason_code: str,
    retry_allowed: bool,
    remediation: str,
    details: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": AGENT_FEEDBACK_SCHEMA_VERSION,
        "failure_type": str(failure_type),
        "layer": str(layer),
        "reason_code": str(reason_code),
        "retry_allowed": bool(retry_allowed),
        "remediation": str(remediation),
        "details": dict(details),
    }


def build_agent_feedback_success(*, stage: str, intent: str, correlation_id: str) -> Dict[str, Any]:
    return build_agent_feedback_envelope(
        failure_type="none",
        layer=stage,
        reason_code=AGENT_FEEDBACK_REASON_OK,
        retry_allowed=False,
        remediation="Proceed to next execution stage.",
        details={"intent": intent, "correlation_id": correlation_id},
    )


def build_failure_protocol_from_agent_feedback_projection(
    *,
    failure_layer: str,
    failure_type: str,
    agent_feedback: Mapping[str, Any],
    details: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    retryable = bool(agent_feedback.get("retry_allowed", False))
    feedback_details = agent_feedback.get("details")
    details_map = feedback_details if isinstance(feedback_details, Mapping) else {}
    fallback_error = details_map.get("error_code")
    if fallback_error is None:
        fallback_error = agent_feedback.get("error_code")
    reason_code = canonicalize_reason_code(
        agent_feedback.get("reason_code"),
        fallback_error_code=fallback_error,
    )
    taxon = lookup_reason_taxon(reason_code)
    failure_type_canonical = canonicalize_failure_type(
        failure_type,
        fallback_reason_code=reason_code,
    )
    resolution_raw = agent_feedback.get("resolution_for_agent")
    if resolution_raw is None and isinstance(details_map, Mapping):
        resolution_raw = details_map.get("resolution_for_agent")
    if resolution_raw is not None and str(resolution_raw).strip():
        repair_hint = str(resolution_raw)
    elif agent_feedback.get("remediation") is not None:
        repair_hint = str(agent_feedback.get("remediation"))
    else:
        repair_hint = str(taxon.default_remediation)
    merged_details = dict(details or {})
    merged_details.setdefault("agent_feedback", dict(agent_feedback))
    merged_details.setdefault("canonical_reason_code", reason_code)
    return {
        "schema_version": FAILURE_PROTOCOL_SCHEMA_VERSION,
        "failure_layer": failure_layer,
        "failure_type": failure_type_canonical,
        "failure_type_canonical": failure_type_canonical,
        "retryable": retryable,
        "repair_hint": repair_hint,
        "human_action_required": (
            (not retryable)
            if taxon.reason_code == "LIRIX_REASON_UNKNOWN"
            else bool(taxon.human_action_required)
        ),
        "details": merged_details,
    }


def resolve_failure_protocol_to_agent_feedback_projection(
    protocol: Mapping[str, Any],
) -> Dict[str, Any]:
    nested = protocol.get("details")
    nested_map: Mapping[str, Any] = nested if isinstance(nested, Mapping) else {}
    inner = nested_map.get("agent_feedback")
    if isinstance(inner, Mapping):
        inner_dict: Dict[str, Any] = dict(inner)
        details = inner_dict.get("details")
        details_map: Mapping[str, Any] = details if isinstance(details, Mapping) else {}
        fallback_error = details_map.get("error_code")
        if fallback_error is None:
            fallback_error = inner_dict.get("error_code")
        reason_code = canonicalize_reason_code(
            inner_dict.get("reason_code"),
            fallback_error_code=fallback_error,
        )
        failure_type = canonicalize_failure_type("", fallback_reason_code=reason_code)
        if failure_type == "unknown":
            failure_type = canonicalize_failure_type(
                inner_dict.get("failure_type"),
                fallback_reason_code=reason_code,
            )
        return build_agent_feedback_envelope(
            failure_type=failure_type,
            layer=str(inner_dict.get("layer", protocol.get("failure_layer", "unknown"))),
            reason_code=reason_code,
            retry_allowed=bool(inner_dict.get("retry_allowed", protocol.get("retryable", False))),
            remediation=str(inner_dict.get("remediation", protocol.get("repair_hint", "blocked"))),
            details=dict(details_map),
        )
    retryable = bool(protocol.get("retryable", False))
    raw_reason = ""
    ctx = nested_map.get("context")
    if isinstance(ctx, Mapping):
        r = ctx.get("reason")
        if isinstance(r, str) and r.strip():
            raw_reason = r.strip().lower()
    if not raw_reason:
        frc = nested_map.get("canonical_reason_code")
        if isinstance(frc, str) and frc.strip():
            raw_reason = frc.strip()
    if not raw_reason:
        ft = protocol.get("failure_type")
        if isinstance(ft, str) and ft.strip():
            raw_reason = ft.strip().lower()
    reason_code = canonicalize_reason_code(
        raw_reason,
        fallback_error_code=nested_map.get("error_code"),
    )
    failure_type_raw = protocol.get(
        "failure_type_canonical",
        protocol.get("failure_type", "unknown"),
    )
    failure_type = canonicalize_failure_type(failure_type_raw, fallback_reason_code=reason_code)
    return build_agent_feedback_envelope(
        failure_type=failure_type,
        layer=str(protocol.get("failure_layer", "unknown")),
        reason_code=reason_code,
        retry_allowed=retryable,
        remediation=str(protocol.get("repair_hint", "blocked")),
        details=dict(nested_map),
    )
