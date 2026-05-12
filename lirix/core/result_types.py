# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Typed shapes for high-level client result surfaces (additive-only)."""

from __future__ import annotations

from typing import Any, Mapping, Optional, TypedDict


class LirixBroadcastFields(TypedDict):
    """Broadcast-oriented fields read from ``result[\"payload\"]``."""

    to: Optional[str]
    data: Optional[str]
    value: int


class AgentFeedbackResult(TypedDict, total=False):
    schema_version: str
    failure_type: str
    layer: str
    reason_code: str
    retry_allowed: bool
    remediation: str
    details: Mapping[str, Any]


class LirixPipelineResult(TypedDict, total=False):
    status: str
    decision: str
    validated: bool
    payload: Mapping[str, Any]
    simulation_ok: bool
    simulation_outcome: Mapping[str, Any]
    policy_decision: Mapping[str, Any]
    agent_feedback: AgentFeedbackResult
    validation_session: Mapping[str, Any]
    replay_bundle: Mapping[str, Any]
    forensic_bundle: Mapping[str, Any]
    security_trace: Mapping[str, Any]
    evidence_schema_version: str
    evidence_v2: Mapping[str, Any]
    migration_modes: Mapping[str, str]
    governance: Mapping[str, Any]
    audit: Mapping[str, Any]
