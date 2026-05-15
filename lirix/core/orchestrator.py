from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Literal, Mapping, NoReturn, Optional, Protocol
from uuid import uuid4

from typing_extensions import TypeAlias
from web3.types import StateOverride

from lirix.core.client_components import (
    ClientPipelineProtocol,
    error_to_feedback_mapper,
    request_normalization,
    result_envelope_builder,
)
from lirix.core.constants import (
    HOOK_ISOLATED_TIMEOUT_SEC,
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
)
from lirix.core.contracts import build_agent_feedback_success
from lirix.core.evidence import (
    ExecutionEvidence,
    SecurityTrace,
    rejected_step_to_agent_feedback,
    simulation_outcome_embedding,
)
from lirix.core.exceptions import HookExecutionException, LirixBaseException
from lirix.core.failure_protocol import build_failure_protocol_from_agent_feedback
from lirix.core.hook_manager import HookManager
from lirix.core.layer_ports import RpcEvidenceSource
from lirix.core.session import ValidationSession, ensure_session
from lirix.core.trace_recorder import TraceRecorder

HookResult: TypeAlias = list[dict[str, Any]]
RunKind: TypeAlias = Literal[
    "validate_and_simulate",
    "async_validate_and_simulate",
    "validate_only",
    "async_validate_only",
    "simulate_only",
    "async_simulate_only",
]

logger = logging.getLogger("lirix.core.orchestrator")


class OrchestratorClient(Protocol):
    """Narrow `Lirix` surface for `LirixPipelineOrchestrator` (no `_facade` import)."""

    hooks: HookManager
    _pipeline: ClientPipelineProtocol

    def _ensure_hook_trace_binding(self) -> None: ...

    def _migration_modes(self) -> Mapping[str, str]: ...

    def _config_fingerprint(self) -> str: ...

    def _registry_closure_digest(self) -> str: ...

    def _replay_proof(self) -> Mapping[str, Any]: ...

    def _artifact_digests_base(self) -> Mapping[str, str]: ...

    def _artifact_digests_with_rpc(
        self, *, rpc_snapshot: Mapping[str, Any]
    ) -> Mapping[str, str]: ...

    def _run_l1_l3_validation(
        self, *, intent: str, payload: Mapping[str, Any], recorder: TraceRecorder
    ) -> None: ...

    def _mark_session_l1_l3_ok(self, sess: ValidationSession) -> None: ...

    def _success_postlude_and_build_result(
        self,
        *,
        sess: ValidationSession,
        kind: RunKind,
        trace: SecurityTrace,
        manage_session_lifecycle: bool,
        finalization_note: str,
        decision_rationale: str,
        decision_details: Mapping[str, Any],
        artifact_digests: Mapping[str, str],
        payload: Mapping[str, Any],
        audit: Optional[Mapping[str, Any]],
        agent_feedback: Mapping[str, Any],
        evidence_v2: Mapping[str, Any],
    ) -> Dict[str, Any]: ...

    def _ensure_simulate_only_precondition(self, sess: ValidationSession) -> None: ...

    def _build_rpc_manager(self) -> RpcEvidenceSource: ...

    def _l4_orchestration_details(
        self, *, rpc: RpcEvidenceSource, block_number: int
    ) -> Mapping[str, Any]: ...

    def _build_sandbox_simulator(self) -> object: ...

    def _run_policy_audit(
        self,
        *,
        payload: Mapping[str, Any],
        simulation_result: Mapping[str, Any],
        security_policy: Optional[Mapping[str, Any]],
        recorder: TraceRecorder,
    ) -> Mapping[str, Any]: ...

    def _record_full_pipeline_success(
        self,
        *,
        kind: RunKind,
        sess: ValidationSession,
        trace: SecurityTrace,
        rpc: RpcEvidenceSource,
        policy_decision: Mapping[str, Any],
    ) -> Dict[str, Any]: ...

    def _build_result(self, **kwargs: Any) -> Dict[str, Any]: ...


class LirixPipelineOrchestrator:
    """Stateless orchestration engine for Lirix client pipelines."""

    @staticmethod
    def _has_blocking_hook_result(results: HookResult) -> Optional[Mapping[str, Any]]:
        for item in results:
            if not bool(item.get("ok", True)) and str(item.get("failure_level", "")) == "fatal":
                return item
        return None

    @staticmethod
    def _raise_if_hook_blocked(
        blocking: Optional[Mapping[str, Any]], *, simulation: bool = False
    ) -> None:
        if blocking is None:
            return
        msg = (
            "Blocking hook decision rejected simulation."
            if simulation
            else "Blocking hook decision rejected payload."
        )
        raise HookExecutionException(
            human_readable_reason=msg,
            context={
                "layer": "hooks",
                "reason": "hook_blocked",
                "hook_result": dict(blocking),
            },
        )

    @staticmethod
    def _simulation_payload(
        out: Mapping[str, Any],
        *,
        validated: bool = False,
        policy_decision: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            **dict(out),
            "simulation_ok": bool(out.get("simulation_ok", False)),
            "simulation_outcome": dict(out),
        }
        if validated:
            payload["validated"] = True
        if policy_decision is not None:
            payload["policy_decision"] = dict(policy_decision)
        return payload

    @staticmethod
    def _start_request(
        *,
        client: OrchestratorClient,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession],
    ) -> Dict[str, Any]:
        sess = ensure_session(session)
        manage_session_lifecycle = session is None
        correlation_id = str(uuid4())
        sess.link_trace(correlation_id)
        request = request_normalization(
            session=sess,
            manage_session_lifecycle=manage_session_lifecycle,
            correlation_id=correlation_id,
            intent=intent,
            payload=payload,
        )
        client.hooks.bind_trace_recorder(request.recorder)
        client._ensure_hook_trace_binding()
        return {
            "sess": sess,
            "manage_session_lifecycle": manage_session_lifecycle,
            "correlation_id": correlation_id,
            "request": request,
        }

    @staticmethod
    def _record_failure(
        client: OrchestratorClient,
        *,
        sess: ValidationSession,
        kind: RunKind,
        trace: SecurityTrace,
        intent: str,
        correlation_id: str,
        exc: LirixBaseException,
        manage_session_lifecycle: bool,
        blocked_note: str,
        recorder: TraceRecorder,
    ) -> NoReturn:
        logger.error(f"Lirix pipeline execution blocked/failed: {exc}", exc_info=True)
        failure_context = error_to_feedback_mapper(exc)
        recorder.record_step(
            ExecutionEvidence(
                layer=str(failure_context.get("layer", "unknown")),
                stage="failed",
                status="rejected",
                reason=str(failure_context.get("reason", exc.error_code)),
                details={
                    "error_code": exc.error_code,
                    "value_protected": exc.value_protected,
                    "context": failure_context,
                },
            )
        )
        agent_feedback = rejected_step_to_agent_feedback(
            trace,
            intent=intent,
            correlation_id=correlation_id,
            exc=exc,
            failure_context=failure_context,
        )
        failure_context["agent_feedback"] = (
            dict(agent_feedback) if isinstance(agent_feedback, Mapping) else {}
        )
        sess.record_trace(
            kind=kind,
            trace=trace.to_dict(),
            status="rejected",
            include_full_trace=False,
            migration_modes=client._migration_modes(),
            config_fingerprint=client._config_fingerprint(),
            registry_closure_digest=client._registry_closure_digest(),
            replay_proof=client._replay_proof(),
        )
        sess.record_decision(
            verdict="blocked",
            rationale=str(getattr(exc, "resolution_for_agent", "blocked")),
            details={
                "intent": intent,
                "correlation_id": correlation_id,
                "error_code": getattr(exc, "error_code", None),
                "value_protected": getattr(exc, "value_protected", None),
                "context": dict(failure_context),
            },
        )
        if manage_session_lifecycle:
            sess.finalize(outcome="rejected", notes=blocked_note)
        agent_fb_mapping: Mapping[str, Any] = (
            agent_feedback if isinstance(agent_feedback, Mapping) else {}
        )
        agent_fb_dict = dict(agent_fb_mapping)
        failure_context = client._pipeline.failures.enrich(
            failure_context=failure_context,
            security_trace=trace.to_dict(),
            agent_feedback=agent_fb_dict,
            replay_bundle=sess.replay_bundle(),
            forensic_bundle=sess.forensic_bundle(),
            validation_session=sess.snapshot(),
            failure_protocol=build_failure_protocol_from_agent_feedback(
                failure_layer=str(failure_context.get("layer", "unknown")),
                failure_type=str(
                    agent_fb_mapping.get("failure_type")
                    or failure_context.get("reason", exc.error_code)
                ),
                agent_feedback=agent_fb_dict,
                details=failure_context,
            ),
        )
        exc.context = failure_context
        raise exc

    async def _run_async_template_pipeline(
        self,
        *,
        client: OrchestratorClient,
        kind: RunKind,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession],
        blocked_note: str,
        runner: Callable[..., Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        sess = ensure_session(session)
        manage_session_lifecycle = session is None
        correlation_id = str(uuid4())
        sess.link_trace(correlation_id)
        request = request_normalization(
            session=sess,
            manage_session_lifecycle=manage_session_lifecycle,
            correlation_id=correlation_id,
            intent=intent,
            payload=payload,
        )
        trace = request.trace
        recorder = request.recorder
        client.hooks.bind_trace_recorder(recorder)
        client._ensure_hook_trace_binding()
        try:
            result = await runner(
                sess=sess,
                manage_session_lifecycle=manage_session_lifecycle,
                correlation_id=correlation_id,
                trace=trace,
                recorder=recorder,
                draft=request.draft_payload,
            )
            return result
        except LirixBaseException as exc:
            self._record_failure(
                client,
                sess=sess,
                kind=kind,
                trace=trace,
                intent=intent,
                correlation_id=correlation_id,
                exc=exc,
                manage_session_lifecycle=manage_session_lifecycle,
                blocked_note=blocked_note,
                recorder=recorder,
            )
        finally:
            client.hooks.bind_trace_recorder(None)
        raise AssertionError("unreachable")  # pragma: no cover

    async def run_validate(
        self,
        *,
        client: OrchestratorClient,
        kind: RunKind,
        stage: str,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession],
        invoke_hooks: Callable[..., Awaitable[HookResult]],
    ) -> Dict[str, Any]:
        async def _runner(**ctx: Any) -> Dict[str, Any]:
            sess = ctx["sess"]
            manage_session_lifecycle = bool(ctx["manage_session_lifecycle"])
            correlation_id = str(ctx["correlation_id"])
            trace = ctx["trace"]
            recorder = ctx["recorder"]
            draft = ctx["draft"]
            pre = await invoke_hooks(
                HOOK_PRE_VALIDATE,
                intent=intent,
                payload=draft,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(self._has_blocking_hook_result(pre), simulation=False)
            client._run_l1_l3_validation(intent=intent, payload=draft, recorder=recorder)
            post = await invoke_hooks(
                HOOK_POST_VALIDATE,
                intent=intent,
                payload=draft,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(self._has_blocking_hook_result(post), simulation=False)
            client._mark_session_l1_l3_ok(sess)
            result = client._success_postlude_and_build_result(
                sess=sess,
                kind=kind,
                trace=trace,
                manage_session_lifecycle=manage_session_lifecycle,
                finalization_note=f"{kind} completed",
                decision_rationale="Validation passed (L1-L3).",
                decision_details={"intent": intent, "correlation_id": correlation_id},
                artifact_digests=client._artifact_digests_base(),
                payload=result_envelope_builder(payload={"validated": True}),
                audit=None,
                agent_feedback=build_agent_feedback_success(
                    stage=stage, intent=intent, correlation_id=correlation_id
                ),
                evidence_v2=client._pipeline.evidence.validate_only(intent=intent),
            )
            return result

        return await self._run_async_template_pipeline(
            client=client,
            kind=kind,
            intent=intent,
            payload=payload,
            session=session,
            blocked_note=f"{kind} blocked",
            runner=_runner,
        )

    async def run_simulate(
        self,
        *,
        client: OrchestratorClient,
        kind: RunKind,
        stage: str,
        payload: Mapping[str, Any],
        state_overrides: Optional[StateOverride],
        session: Optional[ValidationSession],
        invoke_hooks: Callable[..., Awaitable[HookResult]],
        reconcile: Callable[[RpcEvidenceSource], Awaitable[int]],
        get_web3: Callable[[RpcEvidenceSource], Awaitable[Any]],
        simulate: Callable[
            [Any, Mapping[str, Any], int, Optional[StateOverride]], Awaitable[Dict[str, Any]]
        ],
    ) -> Dict[str, Any]:
        sess = ensure_session(session)
        client._ensure_simulate_only_precondition(sess)

        async def _runner(**ctx: Any) -> Dict[str, Any]:
            sess = ctx["sess"]
            manage_session_lifecycle = bool(ctx["manage_session_lifecycle"])
            correlation_id = str(ctx["correlation_id"])
            trace = ctx["trace"]
            recorder = ctx["recorder"]
            draft = ctx["draft"]
            pre = await invoke_hooks(
                HOOK_PRE_SIMULATION,
                intent="simulate_only",
                payload=draft,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(self._has_blocking_hook_result(pre), simulation=True)
            rpc = client._build_rpc_manager()
            block_number = await reconcile(rpc)
            l4_details = client._l4_orchestration_details(rpc=rpc, block_number=block_number)
            recorder.record_step(
                ExecutionEvidence(
                    layer="L4", stage="rpc_reconcile", status="ok", details=dict(l4_details)
                )
            )
            web3_client = await get_web3(rpc)
            out = await simulate(web3_client, draft, block_number, state_overrides)
            sim_embed = simulation_outcome_embedding(out=out)
            recorder.record_step(
                ExecutionEvidence(
                    layer="L5",
                    stage="sandbox_simulation",
                    status="ok",
                    details={"outcome": sim_embed},
                )
            )
            post = await invoke_hooks(
                HOOK_POST_SIMULATION,
                intent="simulate_only",
                payload=draft,
                simulation=out,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(self._has_blocking_hook_result(post), simulation=True)
            result = client._success_postlude_and_build_result(
                sess=sess,
                kind=kind,
                trace=trace,
                manage_session_lifecycle=manage_session_lifecycle,
                finalization_note=f"{kind} completed",
                decision_rationale="Simulation completed (L4-L5 facts only).",
                decision_details={
                    "correlation_id": correlation_id,
                    "simulation_ok": out.get("simulation_ok", False),
                },
                artifact_digests=client._artifact_digests_with_rpc(
                    rpc_snapshot=rpc.evidence_snapshot()
                ),
                payload=result_envelope_builder(
                    payload=self._simulation_payload(out, validated=True)
                ),
                audit={"simulation_ok": bool(out.get("simulation_ok", False))},
                agent_feedback=build_agent_feedback_success(
                    stage=stage, intent="simulate_only", correlation_id=correlation_id
                ),
                evidence_v2=client._pipeline.evidence.simulate_only(
                    l4_details=l4_details, l5_details={"outcome": sim_embed}
                ),
            )
            return result

        return await self._run_async_template_pipeline(
            client=client,
            kind=kind,
            intent="simulate_only",
            payload=payload,
            session=session,
            blocked_note=f"{kind} blocked",
            runner=_runner,
        )

    async def run_full(
        self,
        *,
        client: OrchestratorClient,
        kind: RunKind,
        decision_rationale: str,
        finalization_note: str,
        intent: str,
        payload: Mapping[str, Any],
        state_overrides: Optional[StateOverride],
        security_policy: Optional[Mapping[str, Any]],
        session: Optional[ValidationSession],
        invoke_hooks: Callable[..., Awaitable[HookResult]],
        reconcile: Callable[[RpcEvidenceSource], Awaitable[int]],
        get_web3: Callable[[RpcEvidenceSource], Awaitable[Any]],
        simulate: Callable[
            [Any, Mapping[str, Any], int, Optional[StateOverride]], Awaitable[Dict[str, Any]]
        ],
        agent_feedback_stage: str,
    ) -> Dict[str, Any]:
        run = self._start_request(client=client, intent=intent, payload=payload, session=session)
        sess = run["sess"]
        manage_session_lifecycle = bool(run["manage_session_lifecycle"])
        correlation_id = str(run["correlation_id"])
        request = run["request"]
        trace = request.trace
        recorder = request.recorder
        draft = request.draft_payload
        try:
            pre_validate_hook = await invoke_hooks(
                HOOK_PRE_VALIDATE,
                intent=intent,
                payload=draft,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(
                self._has_blocking_hook_result(pre_validate_hook), simulation=False
            )
            client._run_l1_l3_validation(intent=intent, payload=draft, recorder=recorder)
            client._mark_session_l1_l3_ok(sess)
            pre_sim_hook = await invoke_hooks(
                HOOK_PRE_SIMULATION,
                intent=intent,
                payload=draft,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(
                self._has_blocking_hook_result(pre_sim_hook), simulation=True
            )
            # Re-run L1–L3 on the same normalized draft after pre-simulation hooks.
            # Fail-closed: blocks L4/L5 if validation regresses post-hook.
            client._run_l1_l3_validation(intent=intent, payload=draft, recorder=recorder)
            rpc = client._build_rpc_manager()
            block_number = await reconcile(rpc)
            l4_details = client._l4_orchestration_details(rpc=rpc, block_number=block_number)
            recorder.record_step(
                ExecutionEvidence(
                    layer="L4", stage="rpc_reconcile", status="ok", details=dict(l4_details)
                )
            )
            web3_client = await get_web3(rpc)
            _ = client._build_sandbox_simulator()
            out = await simulate(web3_client, draft, block_number, state_overrides)
            sim_embed = simulation_outcome_embedding(out=out)
            recorder.record_step(
                ExecutionEvidence(
                    layer="L5",
                    stage="sandbox_simulation",
                    status="ok",
                    details={"outcome": sim_embed},
                )
            )
            auditor = client._run_policy_audit(
                payload=draft,
                simulation_result=out,
                security_policy=security_policy,
                recorder=recorder,
            )
            post_sim_hook = await invoke_hooks(
                HOOK_POST_SIMULATION,
                intent=intent,
                payload=draft,
                simulation=out,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(
                self._has_blocking_hook_result(post_sim_hook), simulation=True
            )
            post_validate_full = await invoke_hooks(
                HOOK_POST_VALIDATE,
                intent=intent,
                payload=draft,
                simulation=out,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
            self._raise_if_hook_blocked(
                self._has_blocking_hook_result(post_validate_full), simulation=True
            )
            t = client._record_full_pipeline_success(
                kind=kind, sess=sess, trace=trace, rpc=rpc, policy_decision=auditor
            )
            sess.record_decision(
                verdict="approved",
                rationale=decision_rationale,
                details={
                    "intent": intent,
                    "correlation_id": correlation_id,
                    "policy_decision": auditor,
                },
            )
            if manage_session_lifecycle:
                sess.finalize(outcome="ok", notes=finalization_note)
            result = client._build_result(
                status="approved",
                decision="approved",
                payload=result_envelope_builder(
                    payload=self._simulation_payload(out, validated=True, policy_decision=auditor)
                ),
                audit={"simulation_ok": bool(out.get("simulation_ok", False))},
                agent_feedback=build_agent_feedback_success(
                    stage=agent_feedback_stage, intent=intent, correlation_id=correlation_id
                ),
                validation_session=sess.snapshot(),
                replay_bundle=sess.replay_bundle(),
                forensic_bundle=sess.forensic_bundle(),
                security_trace=t,
                evidence_schema_version=trace.trace_version,
                evidence_v2=client._pipeline.evidence.validate_and_simulate(
                    l4_details=l4_details, l5_details={"outcome": sim_embed}, policy_details=auditor
                ),
            )
            return result
        except LirixBaseException as exc:
            self._record_failure(
                client,
                sess=sess,
                kind=kind,
                trace=trace,
                intent=intent,
                correlation_id=correlation_id,
                exc=exc,
                manage_session_lifecycle=manage_session_lifecycle,
                blocked_note=f"{kind} blocked",
                recorder=recorder,
            )
        finally:
            client.hooks.bind_trace_recorder(None)
