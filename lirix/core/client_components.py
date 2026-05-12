from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from lirix.core.evidence import (
    SecurityTrace,
    build_simulate_only_evidence_v2,
    build_unified_pipeline_evidence_v2,
    build_validate_only_evidence_v2,
)
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session import ValidationSession
from lirix.core.trace_recorder import TraceRecorder
from lirix.layers import RPCManager, SandboxSimulator

# --- Request trace / normalization (single internal pipeline surface) ---


@dataclass(frozen=True)
class RequestContext:
    session: ValidationSession
    manage_session_lifecycle: bool
    correlation_id: str
    trace: SecurityTrace
    recorder: TraceRecorder
    draft_payload: Dict[str, Any]


def request_normalization(
    *,
    session: ValidationSession,
    manage_session_lifecycle: bool,
    correlation_id: str,
    intent: str,
    payload: Mapping[str, Any],
) -> RequestContext:
    trace = SecurityTrace.new(
        correlation_id=correlation_id,
        session_id=session.session_id,
        intent=intent,
        payload=payload,
    )
    try:
        draft_payload = copy.deepcopy(dict(payload))
    except copy.Error as exc:
        raise ConfigurationGuardException(
            human_readable_reason=(
                "Pipeline payload must be deep-copyable (JSON-like nesting only). "
                "Remove non-copyable objects from the payload mapping."
            ),
            context={"reason": "payload_deepcopy_failed"},
        ) from exc
    return RequestContext(
        session=session,
        manage_session_lifecycle=manage_session_lifecycle,
        correlation_id=correlation_id,
        trace=trace,
        recorder=TraceRecorder(trace=trace),
        draft_payload=draft_payload,
    )


def error_to_feedback_mapper(exc: Any) -> Dict[str, Any]:
    context = getattr(exc, "context", None)
    if isinstance(context, dict):
        return dict(context)
    return {"raw": context}


def pipeline_orchestrator(
    *,
    chain_context: Mapping[str, Any],
    runtime_semantics: Mapping[str, Any],
    quorum_verdict: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "chain_context": dict(chain_context),
        "runtime_semantics": dict(runtime_semantics),
        "quorum_verdict": dict(quorum_verdict),
    }


def result_envelope_builder(
    *,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    return dict(payload)


# --- Layer adapters & envelope builders ---


@dataclass(frozen=True)
class PipelineExecutor:
    request_timeout: int
    backend_profile: Mapping[str, Any]

    def build_rpc_manager(self, config: Any, hooks: Any) -> RPCManager:
        return RPCManager(config, hooks=hooks, request_timeout=self.request_timeout)

    def build_sandbox_simulator(self, hooks: Any) -> SandboxSimulator:
        return SandboxSimulator(hooks=hooks, backend_profile=dict(self.backend_profile))


@dataclass(frozen=True)
class EvidenceAssembler:
    def validate_only(self, *, intent: str) -> Dict[str, Any]:
        return build_validate_only_evidence_v2(intent=intent)

    def simulate_only(
        self,
        *,
        l4_details: Mapping[str, Any],
        l5_details: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return build_simulate_only_evidence_v2(
            l4_details=dict(l4_details),
            l5_details=dict(l5_details),
        )

    def validate_and_simulate(
        self,
        *,
        l4_details: Mapping[str, Any],
        l5_details: Mapping[str, Any],
        policy_details: Mapping[str, Any],
    ) -> Dict[str, Any]:
        return build_unified_pipeline_evidence_v2(
            l4_details=dict(l4_details),
            l5_details=dict(l5_details),
            policy_details=dict(policy_details),
        )


@dataclass(frozen=True)
class ResultBuilder:
    def build_base_result(
        self,
        *,
        status: str,
        decision: str,
        agent_feedback: Mapping[str, Any],
        validation_session: Mapping[str, Any],
        replay_bundle: Mapping[str, Any],
        forensic_bundle: Mapping[str, Any],
        security_trace: Mapping[str, Any],
        evidence_schema_version: str,
        evidence_v2: Mapping[str, Any],
        migration_modes: Mapping[str, str],
        payload: Mapping[str, Any] | None = None,
        audit: Mapping[str, Any] | None = None,
        governance: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "status": status,
            "decision": decision,
            "validated": bool((payload or {}).get("validated", status == "approved")),
            "agent_feedback": dict(agent_feedback),
            "validation_session": dict(validation_session),
            "replay_bundle": dict(replay_bundle),
            "forensic_bundle": dict(forensic_bundle),
            "security_trace": dict(security_trace),
            "evidence_schema_version": evidence_schema_version,
            "evidence_v2": dict(evidence_v2),
            "migration_modes": dict(migration_modes),
        }
        if payload is not None:
            payload_dict = dict(payload)
            out["payload"] = payload_dict
            for key in ("validated", "simulation_ok", "simulation_outcome", "policy_decision"):
                if key in payload_dict:
                    out[key] = payload_dict[key]
        if audit is not None:
            out["audit"] = dict(audit)
        if governance is not None:
            out["governance"] = dict(governance)
        return out


@dataclass(frozen=True)
class FailureContextEnricher:
    def enrich(
        self,
        *,
        failure_context: Dict[str, Any],
        security_trace: Mapping[str, Any],
        agent_feedback: Mapping[str, Any],
        replay_bundle: Mapping[str, Any],
        forensic_bundle: Mapping[str, Any],
        validation_session: Mapping[str, Any],
        failure_protocol: Mapping[str, Any],
    ) -> Dict[str, Any]:
        out = dict(failure_context)
        out["security_trace"] = dict(security_trace)
        out["agent_feedback"] = dict(agent_feedback)
        out["replay_bundle"] = dict(replay_bundle)
        out["forensic_bundle"] = dict(forensic_bundle)
        out["validation_session"] = dict(validation_session)
        out["failure_protocol"] = dict(failure_protocol)
        return out


@dataclass(frozen=True)
class ClientPipelineProtocol:
    """Single internal composition surface for Lirix client pipeline helpers."""

    executor: PipelineExecutor
    evidence: EvidenceAssembler
    results: ResultBuilder
    failures: FailureContextEnricher
