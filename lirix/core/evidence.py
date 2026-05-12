from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, List, Mapping, Optional

from lirix.core.canonical_taxonomy import lookup_reason_taxon
from lirix.core.constants import (
    AGENT_FEEDBACK_SCHEMA_VERSION,
    SECURITY_TRACE_SCHEMA_VERSION,
    canonicalize_failure_type,
    canonicalize_reason_code,
)
from lirix.core.contracts import build_agent_feedback_envelope as _canonical_agent_feedback_builder
from lirix.core.contracts import build_agent_feedback_success as _canonical_agent_feedback_success
from lirix.core.contracts import stable_digest
from lirix.core.exceptions import LirixBaseException

# Canonical schema authority for evidence v2 contracts (legacy schema module merged here).
EVIDENCE_LAYER_V2_SCHEMA_VERSION = "2.0"
EVIDENCE_SCHEMA_V2 = EVIDENCE_LAYER_V2_SCHEMA_VERSION


@dataclass(frozen=True)
class LayerEvidenceV2:
    layer: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = EVIDENCE_SCHEMA_V2

    def to_dict(self) -> Dict[str, Any]:
        return build_layer_evidence_dict_v2(
            layer=self.layer, status=self.status, details=dict(self.details)
        )


def build_layer_evidence_dict_v2(
    *,
    layer: str,
    status: str,
    details: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SCHEMA_V2,
        "layer": layer,
        "status": status,
        "details": dict(details),
    }


def build_layer_evidence_v2(
    *,
    layer: str,
    status: str,
    details: Mapping[str, Any],
) -> Dict[str, Any]:
    return build_layer_evidence_dict_v2(layer=layer, status=status, details=details)


def build_validate_only_evidence_v2(*, intent: str) -> Dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SCHEMA_V2,
        "l1": build_layer_evidence_v2(layer="L1", status="ok", details={"intent": intent}),
        "l2": build_layer_evidence_v2(layer="L2", status="ok", details={}),
        "l3": build_layer_evidence_v2(layer="L3", status="ok", details={}),
    }


def build_simulate_only_evidence_v2(
    *,
    l4_details: Mapping[str, Any],
    l5_details: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SCHEMA_V2,
        "l4": build_layer_evidence_v2(layer="L4", status="ok", details=l4_details),
        "l5": build_layer_evidence_v2(layer="L5", status="ok", details=l5_details),
    }


def build_unified_pipeline_evidence_v2(
    *,
    l4_details: Mapping[str, Any],
    l5_details: Mapping[str, Any],
    policy_details: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SCHEMA_V2,
        "l4": build_layer_evidence_v2(layer="L4", status="ok", details=l4_details),
        "l5": build_layer_evidence_v2(layer="L5", status="ok", details=l5_details),
        "policy": build_layer_evidence_v2(layer="policy", status="ok", details=policy_details),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExecutionEvidence:
    layer: str
    stage: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    timestamp: str = field(default_factory=_utc_now)
    step_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "layer": self.layer,
            "stage": self.stage,
            "status": self.status,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }
        if self.step_id is not None:
            payload["step_id"] = self.step_id
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class QuorumVerdict:
    block_number: int
    selected_rpc_url: str | None
    quorum_ok: bool
    required_votes: int | None = None
    observed_votes: int | None = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "block_number": self.block_number,
            "selected_rpc_url": self.selected_rpc_url,
            "quorum_ok": self.quorum_ok,
            "details": dict(self.details),
        }
        if self.required_votes is not None:
            payload["required_votes"] = self.required_votes
        if self.observed_votes is not None:
            payload["observed_votes"] = self.observed_votes
        return payload


@dataclass(frozen=True)
class RPCDisagreementReport:
    reason: str
    schema_version: str = "2.0"
    taxonomy: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    unreachable_nodes: List[str] = field(default_factory=list)
    timeout_nodes: List[str] = field(default_factory=list)
    stale_nodes: List[str] = field(default_factory=list)
    malformed_nodes: List[str] = field(default_factory=list)
    inconsistent_nodes: List[str] = field(default_factory=list)
    suspiciously_consistent_nodes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "schema_version": self.schema_version,
            "taxonomy": dict(self.taxonomy),
            "unreachable_nodes": list(self.unreachable_nodes),
            "timeout_nodes": list(self.timeout_nodes),
            "stale_nodes": list(self.stale_nodes),
            "malformed_nodes": list(self.malformed_nodes),
            "inconsistent_nodes": list(self.inconsistent_nodes),
            "suspiciously_consistent_nodes": list(self.suspiciously_consistent_nodes),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class SimulationOutcome:
    simulation_ok: bool
    layer: str
    block_number: int | None = None
    return_data: str | None = None
    details: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)
    state_delta_digest: str | None = None
    policy_match_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        derived_state_delta_digest = self.state_delta_digest
        if derived_state_delta_digest is None:
            state_delta = self.details.get("state_delta")
            if isinstance(state_delta, Mapping):
                derived_state_delta_digest = stable_digest(state_delta)
        payload: Dict[str, Any] = {
            "simulation_ok": self.simulation_ok,
            "layer": self.layer,
            "details": dict(self.details),
            "assumptions": list(self.assumptions),
            "policy_match_ids": list(self.policy_match_ids),
        }
        if self.block_number is not None:
            payload["block_number"] = self.block_number
        if self.return_data is not None:
            payload["return_data"] = self.return_data
        if derived_state_delta_digest is not None:
            payload["state_delta_digest"] = derived_state_delta_digest
        return payload


@dataclass(frozen=True)
class PolicyDecision:
    policy_id: str
    policy_version: str
    environment: str
    verdict: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "environment": self.environment,
            "verdict": self.verdict,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class AgentFeedbackEnvelope:
    failure_type: str
    layer: str
    reason_code: str
    retry_allowed: bool
    remediation: str
    details: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = AGENT_FEEDBACK_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "failure_type": self.failure_type,
            "layer": self.layer,
            "reason_code": self.reason_code,
            "retry_allowed": self.retry_allowed,
            "remediation": self.remediation,
            "details": dict(self.details),
        }


@dataclass
class SecurityTrace:
    correlation_id: str
    intent: str
    input_summary: Dict[str, Any]
    payload_summary: Dict[str, Any]
    session_id: str | None = None
    steps: List[ExecutionEvidence] = field(default_factory=list)
    trace_version: str = SECURITY_TRACE_SCHEMA_VERSION
    started_at: str = field(default_factory=_utc_now)

    @classmethod
    def new(
        cls,
        *,
        correlation_id: str,
        intent: str,
        payload: Mapping[str, Any],
        session_id: str | None = None,
    ) -> SecurityTrace:
        payload_dict = dict(payload)
        return cls(
            correlation_id=correlation_id,
            session_id=session_id,
            intent=intent,
            input_summary={"keys": sorted(payload_dict.keys()), "size": len(payload_dict)},
            payload_summary={"digest_sha256": stable_digest(payload_dict)},
        )

    def add_step(self, evidence: ExecutionEvidence) -> str:
        step_id = evidence.step_id or secrets.token_hex(8)
        ev = evidence if evidence.step_id else replace(evidence, step_id=step_id)
        self.steps.append(ev)
        return step_id

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "trace_version": self.trace_version,
            "correlation_id": self.correlation_id,
            "intent": self.intent,
            "input_summary": dict(self.input_summary),
            "payload_summary": dict(self.payload_summary),
            "started_at": self.started_at,
            "steps": [step.to_dict() for step in self.steps],
        }
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        return payload


def trace_digest(trace_payload: Mapping[str, Any]) -> str:
    """Canonical SHA-256 over the full security trace dict."""
    canonical = json.dumps(dict(trace_payload), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def simulation_outcome_embedding(*, out: Mapping[str, Any]) -> Dict[str, Any]:
    """L5 factual outcome for trace/evidence; policy_match_ids remain empty (policy is separate)."""
    return SimulationOutcome(
        simulation_ok=bool(out.get("simulation_ok", False)),
        layer=str(out.get("layer", "L5")),
        block_number=out.get("block_number") if out.get("block_number") is not None else None,
        return_data=out.get("return_data") if isinstance(out.get("return_data"), str) else None,
        details=dict(out),
        assumptions=[
            str(x)
            for x in out.get("simulation_assumptions", out.get("assumptions", []))
            if isinstance(x, str)
        ],
        state_delta_digest=(
            str(out["state_delta_digest"])
            if isinstance(out.get("state_delta_digest"), str)
            else None
        ),
        policy_match_ids=[],
    ).to_dict()


def rejected_step_to_agent_feedback(
    trace: SecurityTrace,
    *,
    intent: str,
    correlation_id: str,
    exc: LirixBaseException,
    failure_context: Mapping[str, Any],
) -> Dict[str, Any]:
    """Agent feedback aligned with the last rejected trace step (includes step_id when present)."""
    raw = str(failure_context.get("reason", exc.error_code)).strip().lower()
    reason_code = canonicalize_reason_code(raw, fallback_error_code=exc.error_code)
    taxon = lookup_reason_taxon(reason_code)
    failure_type = canonicalize_failure_type(raw, fallback_reason_code=reason_code)
    if failure_type == "unknown":
        failure_type = taxon.default_failure_type
    retry_allowed = bool(taxon.retry_allowed)
    remediation_raw = getattr(exc, "resolution_for_agent", None)
    remediation = str(remediation_raw) if remediation_raw else str(taxon.default_remediation)
    layer_from_ctx = str(failure_context.get("layer", "unknown"))
    step_id: Optional[str] = None
    for step in reversed(trace.steps):
        if step.status != "rejected":
            continue
        step_id = step.step_id
        break
    details_fb: Dict[str, Any] = {
        "intent": intent,
        "correlation_id": correlation_id,
        "raw_reason": raw,
        "error_code": exc.error_code,
        "value_protected": exc.value_protected,
        "context": dict(failure_context),
    }
    if step_id is not None:
        details_fb["step_id"] = step_id
    return build_agent_feedback_envelope(
        failure_type=failure_type,
        layer=layer_from_ctx,
        reason_code=reason_code,
        retry_allowed=retry_allowed,
        remediation=remediation,
        details=details_fb,
    )


def build_agent_feedback_envelope(
    *,
    failure_type: str,
    layer: str,
    reason_code: str,
    retry_allowed: bool,
    remediation: str,
    details: Mapping[str, Any],
) -> Dict[str, Any]:
    return _canonical_agent_feedback_builder(
        failure_type=failure_type,
        layer=layer,
        reason_code=reason_code,
        retry_allowed=retry_allowed,
        remediation=remediation,
        details=dict(details),
    )


def build_agent_feedback_success(*, stage: str, intent: str, correlation_id: str) -> Dict[str, Any]:
    return _canonical_agent_feedback_success(
        stage=stage,
        intent=intent,
        correlation_id=correlation_id,
    )
