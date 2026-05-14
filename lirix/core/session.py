from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Mapping, Optional
from uuid import uuid4

from lirix.core.constants import canonicalize_error_code
from lirix.core.contracts import is_hex_digest, stable_digest
from lirix.core.evidence import trace_digest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session_fsm import SessionEvent, SessionFSM, _session_workflow_events_seen
from lirix.core.status_aggregation import aggregate_statuses


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SessionLifecycleState = Literal["open", "running", "finalized"]

TRACE_RECORD_KINDS = frozenset(
    {
        "validate_and_simulate",
        "async_validate_and_simulate",
        "validate_only",
        "async_validate_only",
        "simulate_only",
        "async_simulate_only",
    }
)
TRACE_ALLOWED_STATUS = frozenset({"ok", "rejected"})
SESSION_ALLOWED_STATUS = frozenset({"ok", "rejected", "info"})
SESSION_ALLOWED_EVENT_TYPES = frozenset(
    {"plan", "draft", "tool_call", "decision", "finalize", "annotation"}
)
DECISION_ALLOWED_VERDICTS = frozenset({"approved", "blocked", "info"})
REPLAY_BUNDLE_VERSION: str = "2.0"
FORENSIC_BUNDLE_VERSION: str = "1.0"
ALLOWED_BUNDLE_VERSION_MATRIX = frozenset({(REPLAY_BUNDLE_VERSION, FORENSIC_BUNDLE_VERSION)})
REPLAY_ARTIFACT_ALLOWED_KEYS = frozenset(
    {
        "config_snapshot_digest",
        "rpc_evidence_digest",
        "policy_decision_digest",
        "chain_profile_digest",
    }
)
REPLAY_PROOF_STRICT_REQUIRED_KEYS = (
    "chain_registry_digest",
    "decoder_registry_digest",
    "registry_version",
    "registry_source",
)


def _trace_summary(trace: Dict[str, Any]) -> Dict[str, Any]:
    steps = trace.get("steps", [])
    ok = 0
    rejected = 0
    if isinstance(steps, list):
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get("status") == "ok":
                ok += 1
            if s.get("status") == "rejected":
                rejected += 1
    return {
        "trace_version": trace.get("trace_version"),
        "correlation_id": trace.get("correlation_id"),
        "session_id": trace.get("session_id"),
        "intent": trace.get("intent"),
        "started_at": trace.get("started_at"),
        "ok_steps": ok,
        "rejected_steps": rejected,
    }


@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    objective: str
    steps: List[str] = field(default_factory=list)
    retry_budget: int = 0
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective,
            "steps": list(self.steps),
            "retry_budget": self.retry_budget,
            "constraints": list(self.constraints),
        }


@dataclass
class ValidationSession:
    """会话级安全上下文：用于多轮 Agent 工作流的可追踪生命周期。

    **Not thread/coroutine-safe (shared mutation):** treat each ``ValidationSession``
    as owned by a single concurrent pipeline; sharing one instance across asyncio
    tasks or threads without external serialization can corrupt ``timeline`` / ``state``.

    **Concurrency (industrial disclaimer)**

    This object holds mutable ``timeline`` / ``state`` and is designed for a
    single logical workflow owner. Mutating methods use a ``threading.RLock``
    so concurrent **OS-thread** calls into the public API (for example via
    ``asyncio.to_thread`` fan-out) serialize safely.

    It remains **unsafe** to mutate through aliases without holding that API:
    do not mutate ``timeline`` or ``state`` dicts directly from concurrent
    callers. Cooperative asyncio tasks on one thread interleave only at
    ``await`` boundaries; two coroutines sharing one session can still corrupt
    state if they both mutate across yields—treat one session per concurrent
    pipeline unless you enforce external serialization.

    **Not** a distributed lock: multi-process or multi-host sharing is unsupported.
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=_utc_now)
    correlation_ids: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    _lifecycle: SessionLifecycleState = field(default="open", repr=False)
    _fsm: SessionFSM = field(default_factory=SessionFSM, repr=False)
    workflow_mode: Literal["direct", "agent"] = field(default="direct", repr=False)
    workflow_strict: bool = field(default=False, repr=False)
    _mutation_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        if self.workflow_mode not in {"direct", "agent"}:
            raise ConfigurationGuardException(
                human_readable_reason="ValidationSession workflow_mode must be direct or agent.",
                context={
                    "reason": "session_workflow_mode_invalid",
                    "workflow_mode": self.workflow_mode,
                },
            )
        self.workflow_strict = bool(self.workflow_strict or self.workflow_mode == "agent")

    def _effective_workflow_strict(self) -> bool:
        return bool(self.workflow_strict or self.workflow_mode == "agent")

    def _ensure_not_finalized(self, *, context: str) -> None:
        if self._lifecycle == "finalized":
            raise ConfigurationGuardException(
                human_readable_reason="ValidationSession is finalized; mutation not allowed.",
                context={"reason": "session_lifecycle_violation", "phase": context},
            )

    def link_trace(self, correlation_id: str) -> None:
        with self._mutation_lock:
            self._ensure_not_finalized(context="link_trace")
            if correlation_id and correlation_id not in self.correlation_ids:
                self.correlation_ids.append(correlation_id)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "correlation_ids": list(self.correlation_ids),
            "timeline": list(self.timeline),
            "state": dict(self.state),
            "decision_log": self.decision_log(),
            "lifecycle": self._lifecycle,
            "workflow_mode": self.workflow_mode,
            "workflow_strict": self._effective_workflow_strict(),
        }

    def decision_log(self) -> List[Dict[str, Any]]:
        """Return structured decision events for deterministic replay."""
        out: List[Dict[str, Any]] = []
        for item in self.timeline:
            if not isinstance(item, Mapping):
                continue
            if item.get("kind") != "session_event":
                continue
            if item.get("event_type") != "decision":
                continue
            out.append(dict(item))
        return out

    def _last_trace_metadata(self) -> Dict[str, Any]:
        for item in reversed(self.timeline):
            if not isinstance(item, dict):
                continue
            if item.get("kind") in TRACE_RECORD_KINDS:
                return {
                    "trace_digest": item.get("trace_digest"),
                    "migration_modes": item.get("migration_modes") or {},
                    "config_fingerprint": item.get("config_fingerprint"),
                    "registry_closure_digest": item.get("registry_closure_digest"),
                    "correlation_id": item.get("correlation_id"),
                    "artifact_digests": item.get("artifact_digests") or {},
                    "replay_proof": item.get("replay_proof") or {},
                }
        return {}

    def replay_bundle(self) -> Dict[str, Any]:
        """Produce a replay-ready local bundle (no telemetry side effects)."""
        trace_records = [
            item
            for item in self.timeline
            if isinstance(item, Mapping) and item.get("kind") in TRACE_RECORD_KINDS
        ]
        if trace_records:
            fp_values = {
                str(item.get("config_fingerprint"))
                for item in trace_records
                if item.get("config_fingerprint") is not None
            }
            if len(fp_values) > 1:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "ValidationSession contains inconsistent config_fingerprint across traces."
                    ),
                    context={
                        "reason": "replay_bundle_metadata_drift",
                        "field": "config_fingerprint",
                    },
                )
            closure_values = {
                str(item.get("registry_closure_digest"))
                for item in trace_records
                if item.get("registry_closure_digest") is not None
            }
            if len(closure_values) > 1:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "ValidationSession contains inconsistent "
                        "registry_closure_digest across traces."
                    ),
                    context={
                        "reason": "replay_bundle_metadata_drift",
                        "field": "registry_closure_digest",
                    },
                )
        timeline_payload = {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "correlation_ids": list(self.correlation_ids),
            "timeline": list(self.timeline),
            "state": dict(self.state),
            "workflow_mode": self.workflow_mode,
            "workflow_strict": self._effective_workflow_strict(),
        }
        meta = self._last_trace_metadata()
        migration_modes = dict(meta.get("migration_modes") or {})
        config_fp = meta.get("config_fingerprint")
        registry_closure_digest = meta.get("registry_closure_digest")
        last_trace_digest = meta.get("trace_digest")
        artifact_digests = dict(meta.get("artifact_digests") or {})
        replay_proof = dict(meta.get("replay_proof") or {})

        digest_payload: Dict[str, Any] = {
            "bundle_version": REPLAY_BUNDLE_VERSION,
            "migration_modes": migration_modes,
            "config_fingerprint": config_fp,
            "last_trace_digest": last_trace_digest,
            "artifact_digests": artifact_digests,
            "replay_proof": replay_proof,
            "payload": timeline_payload,
        }
        if registry_closure_digest is not None:
            digest_payload["registry_closure_digest"] = str(registry_closure_digest)
        bundle_digest = stable_digest(digest_payload)
        out: Dict[str, Any] = {
            "bundle_version": REPLAY_BUNDLE_VERSION,
            "bundle_digest": bundle_digest,
            "migration_modes": migration_modes,
            "config_fingerprint": config_fp,
            "last_trace_digest": last_trace_digest,
            "artifact_digests": artifact_digests,
            "replay_proof": replay_proof,
            "timeline_size": len(self.timeline),
            "decision_count": len(self.decision_log()),
            "payload": timeline_payload,
        }
        if registry_closure_digest is not None:
            out["registry_closure_digest"] = str(registry_closure_digest)
        return out

    def forensic_bundle(self) -> Dict[str, Any]:
        """Return local forensic package for fail-closed investigations."""
        rejected: List[Dict[str, Any]] = []
        error_codes: List[str] = []
        canonical_error_codes: List[str] = []
        agent_reason_codes: List[str] = []
        rb = self.replay_bundle()
        registry_closure_digest = rb.get("registry_closure_digest")
        last_rejected_step: Optional[Dict[str, Any]] = None
        fatal_hook_summary: Optional[Dict[str, Any]] = None

        def _maybe_extract_from_context(ctx: Mapping[str, Any]) -> None:
            nonlocal last_rejected_step, fatal_hook_summary
            if last_rejected_step is None:
                layer = ctx.get("layer")
                reason = ctx.get("reason")
                error_code = ctx.get("error_code")
                if isinstance(layer, str) and layer:
                    last_rejected_step = {
                        "layer": layer,
                        "reason": str(reason) if reason is not None else None,
                        "error_code": (
                            str(error_code) if isinstance(error_code, str) and error_code else None
                        ),
                        "correlation_id": (
                            str(ctx.get("correlation_id")) if ctx.get("correlation_id") else None
                        ),
                        "trace_digest": (
                            str(ctx.get("trace_digest")) if ctx.get("trace_digest") else None
                        ),
                        "step_id": str(ctx.get("step_id")) if ctx.get("step_id") else None,
                        "trace_step_ref": (
                            f"{ctx.get('correlation_id')}:{ctx.get('step_id')}"
                            if ctx.get("correlation_id") and ctx.get("step_id")
                            else None
                        ),
                    }
            if fatal_hook_summary is None:
                hook_result = ctx.get("hook_result")
                if isinstance(hook_result, Mapping):
                    failure_level = hook_result.get("failure_level")
                    if str(failure_level) == "fatal":
                        fatal_hook_summary = {
                            "hook_point": hook_result.get("hook_point"),
                            "error_code": hook_result.get("error_code"),
                            "error_type": hook_result.get("error_type"),
                            "failure_level": hook_result.get("failure_level"),
                        }

        for item in self.timeline:
            if not isinstance(item, Mapping):
                continue
            if item.get("status") != "rejected":
                continue
            rejected.append(dict(item))
            if item.get("kind") in TRACE_RECORD_KINDS:
                st_full = item.get("security_trace")
                if isinstance(st_full, dict):
                    for step in st_full.get("steps", []) or []:
                        if isinstance(step, dict) and step.get("status") == "rejected":
                            det = step.get("details", {})
                            if isinstance(det, dict):
                                rc = det.get("error_code")
                                if isinstance(rc, str) and rc:
                                    error_codes.append(rc)
                                    canonical_error_codes.append(canonicalize_error_code(rc))
                ts = item.get("trace_summary")
                if isinstance(ts, dict) and ts.get("rejected_steps"):
                    pass
            payload = item.get("payload", {})
            if isinstance(payload, dict):
                details = payload.get("details", {})
                if isinstance(details, dict):
                    error_code = details.get("error_code")
                    if isinstance(error_code, str) and error_code:
                        error_codes.append(error_code)
                        canonical_error_codes.append(canonicalize_error_code(error_code))
                    ctx_af = details.get("context")
                    if isinstance(ctx_af, dict):
                        af = ctx_af.get("agent_feedback")
                        if isinstance(af, dict):
                            rc = af.get("reason_code")
                            if isinstance(rc, str) and rc:
                                agent_reason_codes.append(rc)
                # If decision events stored contextual details, extract last rejection summary.
                ctx = details.get("context") if isinstance(details, dict) else None
                if isinstance(ctx, Mapping):
                    _maybe_extract_from_context(ctx)

        # Also try to recover from the last blocked decision event, which is the most stable
        # carrier for a fail-closed explanation when full traces are not stored.
        if last_rejected_step is None or fatal_hook_summary is None:
            for item in reversed(self.timeline):
                if not isinstance(item, dict):
                    continue
                if item.get("kind") != "session_event" or item.get("event_type") != "decision":
                    continue
                if item.get("status") != "rejected":
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                det = payload.get("details")
                if not isinstance(det, dict):
                    continue
                ctx = det.get("context")
                if isinstance(ctx, Mapping):
                    _maybe_extract_from_context(ctx)
                break
        fb_out: Dict[str, Any] = {
            "forensic_version": FORENSIC_BUNDLE_VERSION,
            "replay_bundle_version": rb.get("bundle_version"),
            "session_id": self.session_id,
            "rejected_events": rejected,
            "error_codes": sorted(set(error_codes)),
            "raw_error_codes": sorted(set(error_codes)),
            "canonical_error_codes": sorted(set(canonical_error_codes)),
            # Deprecated compatibility aliases; keep until v2 forensic schema migration.
            "reason_codes": sorted(set(error_codes)),
            "canonical_reason_codes": sorted(set(canonical_error_codes)),
            "agent_reason_codes": sorted(set(agent_reason_codes)),
            "deprecated_fields": ["reason_codes", "canonical_reason_codes"],
            "replay_bundle_digest": rb.get("bundle_digest"),
            "last_rejected_step": last_rejected_step,
            "fatal_hook_summary": fatal_hook_summary,
        }
        if registry_closure_digest is not None:
            fb_out["registry_closure_digest"] = str(registry_closure_digest)
        return fb_out

    def record_trace(
        self,
        *,
        kind: Literal[
            "validate_and_simulate",
            "async_validate_and_simulate",
            "validate_only",
            "async_validate_only",
            "simulate_only",
            "async_simulate_only",
        ],
        trace: Dict[str, Any],
        status: Literal["ok", "rejected"],
        include_full_trace: bool = False,
        extra: Optional[Dict[str, Any]] = None,
        migration_modes: Optional[Mapping[str, str]] = None,
        config_fingerprint: Optional[str] = None,
        artifact_digests: Optional[Mapping[str, str]] = None,
        registry_closure_digest: Optional[str] = None,
        replay_proof: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """记录一次调用的可回放证据条目（默认只存摘要以控制体积）。"""
        with self._mutation_lock:
            self._ensure_not_finalized(context="record_trace")
            if status not in TRACE_ALLOWED_STATUS:
                raise ConfigurationGuardException(
                    human_readable_reason="record_trace status must be one of {'ok','rejected'}.",
                    context={"reason": "session_trace_status_invalid", "status": status},
                )
            if self._lifecycle == "open":
                self._lifecycle = "running"
            correlation_id = str(trace.get("correlation_id", ""))
            td = trace_digest(trace)
            steps = trace.get("steps", [])
            trace_step_statuses: List[str] = []
            if isinstance(steps, list):
                for s in steps:
                    if isinstance(s, Mapping):
                        st = s.get("status")
                        if isinstance(st, str) and st:
                            trace_step_statuses.append(st)
            trace_overall_status = aggregate_statuses(trace_step_statuses)
            self._fsm.validate_append(
                lifecycle=self._lifecycle,
                timeline=self.timeline,
                incoming=SessionEvent(kind=str(kind)),
            )
            item: Dict[str, Any] = {
                "timestamp": _utc_now(),
                "kind": kind,
                "status": status,
                "correlation_id": correlation_id,
                "trace_digest": td,
                "trace_summary": _trace_summary(trace),
                "trace_overall_status": trace_overall_status,
            }
            if migration_modes is not None:
                item["migration_modes"] = dict(migration_modes)
            if config_fingerprint is not None:
                item["config_fingerprint"] = str(config_fingerprint)
            if artifact_digests is not None:
                item["artifact_digests"] = {str(k): str(v) for k, v in artifact_digests.items()}
            if registry_closure_digest is not None:
                item["registry_closure_digest"] = str(registry_closure_digest)
            if replay_proof is not None:
                item["replay_proof"] = dict(replay_proof)
            if include_full_trace:
                item["security_trace"] = dict(trace)
            if extra:
                item["extra"] = dict(extra)
            self.timeline.append(item)
            prev = str(self.state.get("session_outcome", "info"))
            self.state["session_outcome"] = aggregate_statuses([prev, trace_overall_status])

    def record_event(
        self,
        *,
        event_type: Literal["plan", "draft", "tool_call", "decision", "finalize", "annotation"],
        payload: Dict[str, Any],
        status: Literal["ok", "rejected", "info"] = "info",
    ) -> None:
        """记录会话生命周期事件（结构化、可回放）。"""
        with self._mutation_lock:
            if event_type not in SESSION_ALLOWED_EVENT_TYPES:
                raise ConfigurationGuardException(
                    human_readable_reason="record_event event_type is invalid.",
                    context={"reason": "session_event_type_invalid", "event_type": event_type},
                )
            if status not in SESSION_ALLOWED_STATUS:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "record_event status must be one of {'ok','rejected','info'}."
                    ),
                    context={"reason": "session_event_status_invalid", "status": status},
                )
            self._fsm.validate_append(
                lifecycle=self._lifecycle,
                timeline=self.timeline,
                incoming=SessionEvent(kind="session_event", event_type=str(event_type)),
                workflow_strict=self._effective_workflow_strict(),
            )
            self.timeline.append(
                {
                    "timestamp": _utc_now(),
                    "kind": "session_event",
                    "event_type": event_type,
                    "status": status,
                    "payload": dict(payload),
                }
            )
            if event_type == "decision" and self._effective_workflow_strict():
                self.state["workflow_decision_state"] = payload.get("verdict")
            prev_out = str(self.state.get("session_outcome", "info"))
            self.state["session_outcome"] = aggregate_statuses([prev_out, str(status)])

    def record_plan(self, *, objective: str, constraints: Optional[List[str]] = None) -> None:
        self.record_event(
            event_type="plan",
            payload={"objective": objective, "constraints": list(constraints or [])},
            status="info",
        )

    def bind_execution_plan(self, plan: ExecutionPlan) -> None:
        with self._mutation_lock:
            self._ensure_not_finalized(context="bind_execution_plan")
            self.state["execution_plan"] = plan.to_dict()
            self.record_event(
                event_type="plan",
                payload={"execution_plan": plan.to_dict()},
                status="info",
            )

    def record_draft(self, *, label: str, content: Dict[str, Any]) -> None:
        self.record_event(
            event_type="draft",
            payload={"label": label, "content": dict(content)},
            status="info",
        )

    def record_tool_call(
        self,
        *,
        tool_name: str,
        input_summary: Dict[str, Any],
        output_summary: Optional[Dict[str, Any]] = None,
        ok: bool = True,
    ) -> None:
        self.record_event(
            event_type="tool_call",
            payload={
                "tool_name": tool_name,
                "input_summary": dict(input_summary),
                "output_summary": dict(output_summary or {}),
            },
            status="ok" if ok else "rejected",
        )

    def record_decision(
        self,
        *,
        verdict: str,
        rationale: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self.workflow_strict or self.workflow_mode == "agent":
            seen = _session_workflow_events_seen(self.timeline)
            if "plan" not in seen or "draft" not in seen:
                raise ConfigurationGuardException(
                    human_readable_reason="Missing FSM prerequisites",
                    context={"reason": "missing_fsm_prerequisites"},
                )
        if verdict not in DECISION_ALLOWED_VERDICTS:
            raise ConfigurationGuardException(
                human_readable_reason="record_decision verdict must be approved, blocked, or info.",
                context={"reason": "session_decision_verdict_invalid", "verdict": verdict},
            )
        self.record_event(
            event_type="decision",
            payload={"verdict": verdict, "rationale": rationale, "details": dict(details or {})},
            status="info" if verdict == "info" else ("ok" if verdict == "approved" else "rejected"),
        )

    def finalize(self, *, outcome: str, notes: Optional[str] = None) -> None:
        with self._mutation_lock:
            self._ensure_not_finalized(context="finalize")
            self.record_event(
                event_type="finalize",
                payload={"outcome": outcome, "notes": notes},
                status="ok" if outcome == "ok" else "rejected",
            )
            self._lifecycle = "finalized"


def new_validation_session_direct() -> ValidationSession:
    """Orchestrator/direct: explicit ``workflow_mode="direct"`` (single construction site)."""

    return ValidationSession(workflow_mode="direct")


def new_validation_session_agent() -> ValidationSession:
    """Agent/integration: ``workflow_mode="agent"`` (strict semantics in ``__post_init__``)."""

    return ValidationSession(workflow_mode="agent")


def ensure_session(session: Optional[ValidationSession]) -> ValidationSession:
    return session if session is not None else new_validation_session_direct()


def verify_replay_bundle(
    bundle: Mapping[str, Any],
    *,
    enforce_workflow_strict: bool = False,
    enforce_replay_proof_strict: bool = False,
    enforce_agent_timeline_order: Optional[bool] = None,
) -> None:
    """Fail-closed integrity check for replay bundles.

    ``enforce_agent_timeline_order`` is a compatibility alias for older call sites.
    When provided, it maps directly onto ``enforce_workflow_strict``.
    """
    bver = bundle.get("bundle_version")
    if bver != REPLAY_BUNDLE_VERSION:
        raise ConfigurationGuardException(
            human_readable_reason=(
                f"Unsupported or missing replay bundle_version (expected {REPLAY_BUNDLE_VERSION})."
            ),
            context={
                "reason": "replay_bundle_version",
                "bundle_version": bver,
                "expected": REPLAY_BUNDLE_VERSION,
            },
        )
    digest_expected = bundle.get("bundle_digest")
    if not isinstance(digest_expected, str):
        raise ConfigurationGuardException(
            human_readable_reason="Replay bundle_digest must be a string.",
            context={"reason": "replay_bundle_malformed"},
        )
    payload = bundle.get("payload")
    if not isinstance(payload, dict):
        raise ConfigurationGuardException(
            human_readable_reason="Replay bundle payload must be an object.",
            context={"reason": "replay_bundle_malformed"},
        )
    mode = payload.get("workflow_mode")
    if mode not in {"agent", "direct"}:
        raise ConfigurationGuardException(
            human_readable_reason=(
                "Replay bundle payload is missing or has an invalid 'workflow_mode'."
            ),
            context={
                "reason": "replay_bundle_workflow_mode_missing_or_invalid",
                "found_mode": mode,
            },
        )
    timeline = payload.get("timeline")
    if not isinstance(timeline, list):
        raise ConfigurationGuardException(
            human_readable_reason="Replay bundle payload.timeline must be a list.",
            context={"reason": "replay_bundle_malformed"},
        )
    if enforce_agent_timeline_order is not None:
        enforce_workflow_strict = bool(enforce_agent_timeline_order)
    saw_finalize = False
    finalize_count = 0
    allowed_status = SESSION_ALLOWED_STATUS
    fsm = SessionFSM()
    replay_timeline: List[Mapping[str, Any]] = []
    for item in timeline:
        if not isinstance(item, Mapping):
            raise ConfigurationGuardException(
                human_readable_reason="Replay bundle timeline entries must be objects.",
                context={"reason": "replay_bundle_malformed"},
            )
        if item.get("kind") != "session_event":
            continue
        event_type = item.get("event_type")
        status = item.get("status")
        if not isinstance(event_type, str) or event_type not in SESSION_ALLOWED_EVENT_TYPES:
            raise ConfigurationGuardException(
                human_readable_reason="Replay timeline contains unknown session event_type.",
                context={"reason": "replay_bundle_timeline_event_type", "event_type": event_type},
            )
        if not isinstance(status, str) or status not in allowed_status:
            raise ConfigurationGuardException(
                human_readable_reason="Replay timeline contains invalid session event status.",
                context={"reason": "replay_bundle_timeline_status", "status": status},
            )
        if enforce_workflow_strict:
            fsm.validate_append(
                lifecycle="running",
                timeline=replay_timeline,
                incoming=SessionEvent(kind="session_event", event_type=event_type),
                workflow_strict=True,
            )
        replay_timeline.append(item)
        if event_type == "finalize":
            saw_finalize = True
            finalize_count += 1
            continue
        if saw_finalize and event_type in {"plan", "draft", "tool_call", "decision"}:
            raise ConfigurationGuardException(
                human_readable_reason="Replay timeline contains session mutations after finalize.",
                context={"reason": "replay_bundle_timeline_order", "event_type": event_type},
            )
    if finalize_count > 1:
        raise ConfigurationGuardException(
            human_readable_reason="Replay timeline contains duplicate finalize events.",
            context={"reason": "replay_bundle_timeline_finalize_duplicate"},
        )
    timeline_size = bundle.get("timeline_size")
    if isinstance(timeline_size, int) and timeline_size != len(timeline):
        raise ConfigurationGuardException(
            human_readable_reason="Replay timeline_size does not match payload.timeline length.",
            context={
                "reason": "replay_bundle_timeline_size_mismatch",
                "timeline_size": timeline_size,
                "actual_timeline_size": len(timeline),
            },
        )
    decision_count = bundle.get("decision_count")
    if isinstance(decision_count, int):
        actual_decision_count = sum(
            1
            for item in timeline
            if isinstance(item, Mapping)
            and item.get("kind") == "session_event"
            and item.get("event_type") == "decision"
        )
        if decision_count != actual_decision_count:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "Replay decision_count does not match payload.timeline decisions."
                ),
                context={
                    "reason": "replay_bundle_decision_count_mismatch",
                    "decision_count": decision_count,
                    "actual_decision_count": actual_decision_count,
                },
            )
    recomputed_obj: Dict[str, Any] = {
        "bundle_version": REPLAY_BUNDLE_VERSION,
        "migration_modes": bundle.get("migration_modes") or {},
        "config_fingerprint": bundle.get("config_fingerprint"),
        "last_trace_digest": bundle.get("last_trace_digest"),
        "artifact_digests": bundle.get("artifact_digests") or {},
        "replay_proof": bundle.get("replay_proof") or {},
        "payload": payload,
    }
    rcd = bundle.get("registry_closure_digest")
    if rcd is not None:
        if not is_hex_digest(rcd):
            raise ConfigurationGuardException(
                human_readable_reason="registry_closure_digest must be a 64-char hex digest.",
                context={"reason": "replay_bundle_registry_closure_digest_malformed"},
            )
        recomputed_obj["registry_closure_digest"] = str(rcd)
    config_fingerprint = bundle.get("config_fingerprint")
    if config_fingerprint is not None and not is_hex_digest(config_fingerprint):
        raise ConfigurationGuardException(
            human_readable_reason="config_fingerprint must be a 64-char hex digest.",
            context={"reason": "replay_bundle_config_fingerprint_malformed"},
        )
    last_trace_digest = bundle.get("last_trace_digest")
    if last_trace_digest is not None and not is_hex_digest(last_trace_digest):
        raise ConfigurationGuardException(
            human_readable_reason="last_trace_digest must be a 64-char hex digest.",
            context={"reason": "replay_bundle_last_trace_digest_malformed"},
        )
    artifact_digests = bundle.get("artifact_digests") or {}
    if not isinstance(artifact_digests, Mapping):
        raise ConfigurationGuardException(
            human_readable_reason="artifact_digests must be an object.",
            context={"reason": "replay_bundle_artifact_digests_malformed"},
        )
    for key, value in artifact_digests.items():
        if not isinstance(key, str) or not key:
            raise ConfigurationGuardException(
                human_readable_reason="artifact_digests keys must be non-empty strings.",
                context={"reason": "replay_bundle_artifact_digests_malformed"},
            )
        if key not in REPLAY_ARTIFACT_ALLOWED_KEYS and not key.startswith("ext_"):
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "artifact_digests key is not allowed; use known keys or ext_* namespace."
                ),
                context={"reason": "replay_bundle_artifact_digests_key_not_allowed", "key": key},
            )
        if not is_hex_digest(value):
            raise ConfigurationGuardException(
                human_readable_reason="artifact_digests values must be 64-char hex digests.",
                context={"reason": "replay_bundle_artifact_digests_malformed", "key": key},
            )
    replay_proof = bundle.get("replay_proof") or {}
    if not isinstance(replay_proof, Mapping):
        raise ConfigurationGuardException(
            human_readable_reason="replay_proof must be an object.",
            context={"reason": "replay_bundle_replay_proof_malformed"},
        )
    if enforce_replay_proof_strict:
        missing_keys = [k for k in REPLAY_PROOF_STRICT_REQUIRED_KEYS if k not in replay_proof]
        if missing_keys:
            raise ConfigurationGuardException(
                human_readable_reason="replay_proof is missing required keys in strict mode.",
                context={
                    "reason": "replay_bundle_replay_proof_missing_keys",
                    "missing_keys": missing_keys,
                },
            )
    for key in ("chain_registry_digest", "decoder_registry_digest"):
        val = replay_proof.get(key)
        if val is not None and not is_hex_digest(val):
            raise ConfigurationGuardException(
                human_readable_reason=f"{key} must be a 64-char hex digest when present.",
                context={"reason": "replay_bundle_replay_proof_malformed", "key": key},
            )
    for key in ("registry_version", "registry_source"):
        val = replay_proof.get(key)
        if val is not None and not isinstance(val, str):
            raise ConfigurationGuardException(
                human_readable_reason=f"{key} must be a string when present.",
                context={"reason": "replay_bundle_replay_proof_malformed", "key": key},
            )
    recomputed = stable_digest(recomputed_obj)
    if recomputed != digest_expected:
        raise ConfigurationGuardException(
            human_readable_reason="Replay bundle digest mismatch.",
            context={
                "reason": "replay_bundle_integrity",
                "expected": digest_expected,
                "recomputed": recomputed,
            },
        )
