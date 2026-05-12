from __future__ import annotations

from typing import Any, Dict, Mapping

from lirix.core.contracts import (
    FAILURE_PROTOCOL_SCHEMA_VERSION,
    build_failure_protocol_from_agent_feedback_projection,
    resolve_failure_protocol_to_agent_feedback_projection,
)


def build_failure_protocol(
    *,
    failure_layer: str,
    failure_type: str,
    retryable: bool,
    repair_hint: str,
    human_action_required: bool,
    details: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "schema_version": FAILURE_PROTOCOL_SCHEMA_VERSION,
        "failure_layer": failure_layer,
        "failure_type": failure_type,
        "failure_type_canonical": failure_type,
        "retryable": retryable,
        "repair_hint": repair_hint,
        "human_action_required": human_action_required,
        "details": dict(details or {}),
    }


def build_failure_protocol_from_agent_feedback(
    *,
    failure_layer: str,
    failure_type: str,
    agent_feedback: Mapping[str, Any],
    details: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    return build_failure_protocol_from_agent_feedback_projection(
        failure_layer=failure_layer,
        failure_type=failure_type,
        agent_feedback=agent_feedback,
        details=details,
    )


def resolve_failure_protocol_to_agent_feedback(
    protocol: Mapping[str, Any],
) -> Dict[str, Any]:
    return resolve_failure_protocol_to_agent_feedback_projection(protocol)
