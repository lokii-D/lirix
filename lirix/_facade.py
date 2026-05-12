# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
from typing import Any, Callable, Coroutine, Dict, Mapping, Optional, Sequence, cast

from web3.types import StateOverride

from lirix.audit.logger import AuditLogger
from lirix.core.chain_adapter import ChainAdapter, build_chain_profile
from lirix.core.client_components import (
    ClientPipelineProtocol,
    EvidenceAssembler,
    FailureContextEnricher,
    PipelineExecutor,
    ResultBuilder,
)
from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config
from lirix.core.config_fingerprint import (
    fingerprint_lirix_config,
    fingerprint_registry_closure_bundle,
)
from lirix.core.constants import (
    LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
    normalize_policy_lifecycle_mode,
)
from lirix.core.decoder_registry import DecoderRegistry
from lirix.core.evidence import SecurityTrace
from lirix.core.exceptions import (
    ConfigurationGuardException,
    LirixBaseException,
    LirixSecurityException,
)
from lirix.core.failure_protocol import resolve_failure_protocol_to_agent_feedback
from lirix.core.hook_manager import HookManager
from lirix.core.orchestrator import LirixPipelineOrchestrator, RunKind
from lirix.core.registry_profile_guard import validate_lirix_strict_registry
from lirix.core.session import ValidationSession, verify_replay_bundle
from lirix.core.trace_recorder import TraceRecorder
from lirix.layers.l1_intent_validator import IntentValidator
from lirix.layers.l2_schema_validator import SchemaValidator
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_shadow_auditor import ShadowAuditor


def _sha256_hex_canonical(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Lirix:
    """Thin public facade for the Lirix security boundary."""

    def __init__(
        self,
        config: Optional[LirixConfig] = None,
        *,
        rpc_urls: Optional[Sequence[str]] = None,
        runtime_patch: Optional[Mapping[str, Any]] = None,
    ) -> None:
        resolved, self._config_source_tags = resolve_config(
            config=config, rpc_urls=rpc_urls, runtime_patch=runtime_patch
        )
        self.config = resolved
        validate_lirix_strict_registry(self.config)
        profile = build_chain_profile(self.config.chain_id, self.config.chain_profile)
        decoder_registry = DecoderRegistry()
        for plug in self.config.decoder_plugins:
            decoder_registry.register(plug)
        self.chain_adapter = ChainAdapter(
            profile,
            strict_mode=self.config.strict_mode,
            decoder_registry=decoder_registry,
        )
        rpc_policy = dict(profile.rpc_policy or {})
        rpc_timeout = int(rpc_policy.get("request_timeout", 30))
        self._pipeline = ClientPipelineProtocol(
            executor=PipelineExecutor(
                request_timeout=rpc_timeout,
                backend_profile=self.chain_adapter.simulation_backend_profile(),
            ),
            evidence=EvidenceAssembler(),
            results=ResultBuilder(),
            failures=FailureContextEnricher(),
        )
        self.hooks = HookManager(contract_mode=self.config.hook_contract_mode)
        self.audit = AuditLogger(hook_manager=self.hooks)
        self.orchestrator = LirixPipelineOrchestrator()

    # --- Public API ---

    def validate_only(
        self,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
    ) -> Dict[str, Any]:
        return self._run_coroutine_sync(
            lambda: self.orchestrator.run_validate(
                client=self,
                kind="validate_only",
                stage="validate_only",
                intent=intent,
                payload=payload,
                session=session,
                invoke_hooks=self._invoke_hooks,
            )
        )

    async def async_validate_only(
        self,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
    ) -> Dict[str, Any]:
        return await self.orchestrator.run_validate(
            client=self,
            kind="async_validate_only",
            stage="validate_only",
            intent=intent,
            payload=payload,
            session=session,
            invoke_hooks=self._invoke_hooks,
        )

    def simulate_only(
        self,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
        state_overrides: Optional[StateOverride] = None,
    ) -> Dict[str, Any]:
        return self._run_coroutine_sync(
            lambda: self.orchestrator.run_simulate(
                client=self,
                kind="simulate_only",
                stage="simulate_only",
                payload=payload,
                state_overrides=state_overrides,
                session=session,
                invoke_hooks=self._invoke_hooks,
                reconcile=self._reconcile,
                get_web3=self._get_web3,
                simulate=self._async_simulate,
            )
        )

    async def async_simulate_only(
        self,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
        state_overrides: Optional[StateOverride] = None,
    ) -> Dict[str, Any]:
        return await self.orchestrator.run_simulate(
            client=self,
            kind="async_simulate_only",
            stage="simulate_only",
            payload=payload,
            state_overrides=state_overrides,
            session=session,
            invoke_hooks=self._invoke_hooks,
            reconcile=self._reconcile,
            get_web3=self._get_web3,
            simulate=self._async_simulate,
        )

    def validate_and_simulate(
        self,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
        state_overrides: Optional[StateOverride] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._run_coroutine_sync(
            lambda: self._run_full_pipeline(
                kind="validate_and_simulate",
                intent=intent,
                payload=payload,
                session=session,
                state_overrides=state_overrides,
                security_policy=security_policy,
            )
        )

    async def async_validate_and_simulate(
        self,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession] = None,
        state_overrides: Optional[StateOverride] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await self._run_full_pipeline(
            kind="async_validate_and_simulate",
            intent=intent,
            payload=payload,
            session=session,
            state_overrides=state_overrides,
            security_policy=security_policy,
        )

    async def _run_full_pipeline(
        self,
        *,
        kind: RunKind,
        intent: str,
        payload: Mapping[str, Any],
        session: Optional[ValidationSession],
        state_overrides: Optional[StateOverride],
        security_policy: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        return await self.orchestrator.run_full(
            client=self,
            kind=kind,
            decision_rationale="Validated and simulated.",
            finalization_note="validate_and_simulate completed",
            intent=intent,
            payload=payload,
            state_overrides=state_overrides,
            security_policy=security_policy,
            session=session,
            invoke_hooks=self._invoke_hooks,
            reconcile=self._reconcile,
            get_web3=self._get_web3,
            simulate=self._async_simulate,
            agent_feedback_stage="validate_and_simulate",
        )

    def chain_validate(self, intent: str, payload: Mapping[str, Any]) -> bool:
        draft: Dict[str, Any] = payload if isinstance(payload, dict) else dict(payload)

        IntentValidator(self.config, hooks=self.hooks).validate(intent, draft)
        SchemaValidator(hooks=self.hooks).validate(draft)
        DeFiPayloadParser(self.config, hooks=self.hooks, chain_adapter=self.chain_adapter).validate(
            draft
        )
        return True

    @staticmethod
    def resolve_failure_protocol(exc_or_bundle_context: Mapping[str, Any]) -> Dict[str, Any]:
        if not exc_or_bundle_context:
            return {}
        nested = exc_or_bundle_context.get("failure_protocol")
        if isinstance(nested, Mapping):
            return resolve_failure_protocol_to_agent_feedback(nested)
        return resolve_failure_protocol_to_agent_feedback(exc_or_bundle_context)

    @staticmethod
    def replay_from_bundle(
        bundle: Mapping[str, Any],
        *,
        enforce_workflow_strict: bool = False,
        enforce_replay_proof_strict: bool = False,
    ) -> Mapping[str, Any]:
        verify_replay_bundle(
            bundle,
            enforce_workflow_strict=enforce_workflow_strict,
            enforce_replay_proof_strict=enforce_replay_proof_strict,
        )
        payload = bundle.get("payload")
        return payload if isinstance(payload, Mapping) else {}

    @staticmethod
    def extract_broadcast_fields(result: Mapping[str, Any]) -> Dict[str, Any]:
        decision = result.get("decision")
        status = result.get("status")
        strict_approved = decision == "approved" and status == "approved"
        raw = result.get("payload")
        pl: Dict[str, Any] = dict(raw) if isinstance(raw, Mapping) else {}

        def _coerce_value(v: Any) -> int:
            if isinstance(v, bool):
                return int(v)
            if isinstance(v, int):
                return v
            try:
                return int(cast(Any, v))
            except (TypeError, ValueError):
                return 0

        if not strict_approved:
            return {
                "to": pl.get("to") if pl.get("to") not in (None, "") else None,
                "data": pl.get("data") if pl.get("data") not in (None, "") else None,
                "value": _coerce_value(pl.get("value", 0)),
            }

        value = _coerce_value(pl.get("value", 0))
        to_v = pl.get("to")
        data_v = pl.get("data")
        if to_v is None or (isinstance(to_v, str) and to_v.strip() == ""):
            raise LirixSecurityException(
                error_code=LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
                human_readable_reason="Approved envelope missing broadcast `to`.",
                context={
                    "reason": "approved_broadcast_fields_invariant",
                    "canonical_error_code": LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
                },
            )
        if data_v is None or (isinstance(data_v, str) and data_v.strip() == ""):
            raise LirixSecurityException(
                error_code=LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
                human_readable_reason="Approved envelope missing broadcast `data`.",
                context={
                    "reason": "approved_broadcast_fields_invariant",
                    "canonical_error_code": LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
                },
            )
        return {"to": to_v, "data": data_v, "value": value}

    @staticmethod
    def _has_blocking_hook_result(
        results: list[dict[str, Any]],
    ) -> Optional[Mapping[str, Any]]:
        return LirixPipelineOrchestrator._has_blocking_hook_result(results)

    @staticmethod
    def _raise_if_hook_blocked(
        blocking: Optional[Mapping[str, Any]], *, simulation: bool = False
    ) -> None:
        LirixPipelineOrchestrator._raise_if_hook_blocked(blocking, simulation=simulation)

    def get_agent_resolution(self, result: Mapping[str, Any]) -> Dict[str, Any]:
        af = result.get("agent_feedback")
        return dict(af) if isinstance(af, Mapping) else {}

    def get_repair_instruction(self, result: Mapping[str, Any]) -> str:
        af = result.get("agent_feedback")
        if not isinstance(af, Mapping):
            return "no_repair_instruction"
        rem = af.get("remediation")
        return str(rem) if rem is not None else "no_repair_instruction"

    def build_safe_payload(
        self,
        *,
        to: str,
        data: str,
        function_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        p: Dict[str, Any] = {"to": to, "data": data}
        if function_name is not None:
            p["function_name"] = function_name
        return p

    def _governance_snapshot(self) -> Dict[str, Any]:
        return {"config_source_tags": dict(self.config.config_source_tags)}

    def _decoder_mode(self) -> str:
        prof = self.config.chain_profile
        if isinstance(prof, Mapping):
            dp = prof.get("decoder_plugins")
            if isinstance(dp, list) and len(dp) > 0:
                return "profile_allowlist"
        return "explicit_only"

    def _resolved_decoder_plugins(self) -> list[str]:
        names: list[str] = []
        for p in self.chain_adapter.decoder_plugins():
            n = getattr(p, "name", None)
            if isinstance(n, str) and n:
                names.append(n)
        return names

    def _migration_modes(self) -> Dict[str, str]:
        eff = normalize_policy_lifecycle_mode(str(self.config.policy_lifecycle_mode))
        return {
            "hook_contract_mode": self.config.hook_contract_mode,
            "policy_lifecycle_mode": eff,
            "policy_lifecycle_mode_effective": eff,
            "rpc_evidence_mode": self.config.rpc_evidence_mode,
        }

    def _config_fingerprint(self) -> str:
        return fingerprint_lirix_config(self.config)

    def _registry_closure_digest(self) -> str:
        return fingerprint_registry_closure_bundle(
            chain_registry=self.chain_adapter.registry_snapshot(),
            decoder_registry=self.chain_adapter.decoder_registry_snapshot(),
        )

    def _replay_proof(self) -> Dict[str, str]:
        prof = self.chain_adapter.profile
        cr = self.chain_adapter.registry_snapshot()
        dr = self.chain_adapter.decoder_registry_snapshot()
        return {
            "chain_registry_digest": _sha256_hex_canonical(cr),
            "decoder_registry_digest": _sha256_hex_canonical(dr),
            "registry_version": str(prof.registry_version or "v1"),
            "registry_source": str(prof.registry_source or "chain_adapter"),
        }

    def _artifact_digests_base(self) -> Dict[str, str]:
        return {
            "ext_resolved_decoder_plugins_digest": _sha256_hex_canonical(
                {"names": sorted(self._resolved_decoder_plugins())}
            ),
        }

    def _artifact_digests_with_rpc(self, *, rpc_snapshot: Mapping[str, Any]) -> Dict[str, str]:
        out = dict(self._artifact_digests_base())
        out["rpc_evidence_digest"] = _sha256_hex_canonical(dict(rpc_snapshot))
        return out

    def _resolved_decoder_plugins_digest(self) -> str:
        return _sha256_hex_canonical({"names": sorted(self._resolved_decoder_plugins())})

    def _ensure_hook_trace_binding(self) -> None:
        if not self.hooks.has_bound_trace_recorder():
            raise ConfigurationGuardException(
                human_readable_reason="Hook trace recorder is not bound for this call.",
                context={"reason": "hook_trace_recorder_missing"},
            )

    def _run_coroutine_sync(
        self, factory: Callable[[], Coroutine[Any, Any, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        async def _runner() -> Dict[str, Any]:
            return await factory()

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_runner())

        def _thread_entry() -> Dict[str, Any]:
            return asyncio.run(_runner())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_thread_entry)
            try:
                return fut.result()
            except BaseException as outer:
                cur: BaseException | None = outer
                for _ in range(24):
                    if cur is None:
                        break
                    if isinstance(cur, LirixBaseException):
                        raise cur from None
                    cur = (
                        cur.__cause__
                        if cur.__cause__ is not None
                        else getattr(cur, "__context__", None)
                    )
                raise outer

    async def _invoke_hooks(self, hook_point: str, **kwargs: Any) -> list[dict[str, Any]]:
        timeout_sec = kwargs.pop("timeout_sec", None)
        return await self.hooks.ainvoke_hooks_isolated(
            hook_point, timeout_sec=timeout_sec, **kwargs
        )

    async def _reconcile(self, rpc_manager: Any) -> int:
        return int(await rpc_manager.async_reconcile())

    async def _get_web3(self, rpc_manager: Any) -> Any:
        return rpc_manager.async_web3()

    def _build_rpc_manager(self) -> RPCManager:
        return self._pipeline.executor.build_rpc_manager(self.config, self.hooks)

    def _build_sandbox_simulator(self) -> Any:
        return self._pipeline.executor.build_sandbox_simulator(self.hooks)

    def _l4_orchestration_details(self, *, rpc: RPCManager, block_number: int) -> Dict[str, Any]:
        return {
            "block_number": block_number,
            "rpc_evidence": rpc.evidence_snapshot(),
        }

    def _run_l1_l3_validation(
        self, *, intent: str, payload: Mapping[str, Any], recorder: TraceRecorder
    ) -> None:
        _ = recorder
        self.chain_validate(intent, payload)

    def _mark_session_l1_l3_ok(self, sess: ValidationSession) -> None:
        sess.state["l1_l3_ok"] = True

    def _ensure_simulate_only_precondition(self, sess: ValidationSession) -> None:
        if not self.config.simulate_only_requires_prior_validate:
            return
        if not bool(sess.state.get("l1_l3_ok")):
            raise ConfigurationGuardException(
                human_readable_reason="simulate_only requires prior validate_only on this session.",
                context={"reason": "simulate_only_prior_validate_required"},
            )

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
    ) -> Dict[str, Any]:
        sess.record_trace(
            kind=kind,
            trace=trace.to_dict(),
            status="ok",
            migration_modes=self._migration_modes(),
            config_fingerprint=self._config_fingerprint(),
            artifact_digests=artifact_digests,
            registry_closure_digest=self._registry_closure_digest(),
            replay_proof=self._replay_proof(),
        )
        sess.record_decision(
            verdict="approved",
            rationale=decision_rationale,
            details=dict(decision_details),
        )
        if manage_session_lifecycle:
            sess.finalize(outcome="ok", notes=finalization_note)
        return self._pipeline.results.build_base_result(
            status="approved",
            decision="approved",
            agent_feedback=agent_feedback,
            validation_session=sess.snapshot(),
            replay_bundle=sess.replay_bundle(),
            forensic_bundle=sess.forensic_bundle(),
            security_trace=trace.to_dict(),
            evidence_schema_version=trace.trace_version,
            evidence_v2=evidence_v2,
            migration_modes=self._migration_modes(),
            payload=payload,
            audit=audit,
        )

    def _run_policy_audit(
        self,
        *,
        payload: Mapping[str, Any],
        simulation_result: Mapping[str, Any],
        security_policy: Optional[Mapping[str, Any]],
        recorder: TraceRecorder,
    ) -> Mapping[str, Any]:
        _ = recorder
        auditor = ShadowAuditor(lifecycle_mode=str(self.config.policy_lifecycle_mode))
        auditor.audit(
            payload=payload,
            simulation_result=simulation_result,
            security_policy=security_policy,
        )
        return auditor.decision_report(security_policy=security_policy)

    def _record_full_pipeline_success(
        self,
        *,
        kind: RunKind,
        sess: ValidationSession,
        trace: SecurityTrace,
        rpc: RPCManager,
        policy_decision: Mapping[str, Any],
    ) -> Dict[str, Any]:
        _ = policy_decision
        sess.record_trace(
            kind=kind,
            trace=trace.to_dict(),
            status="ok",
            migration_modes=self._migration_modes(),
            config_fingerprint=self._config_fingerprint(),
            artifact_digests=self._artifact_digests_with_rpc(rpc_snapshot=rpc.evidence_snapshot()),
            registry_closure_digest=self._registry_closure_digest(),
            replay_proof=self._replay_proof(),
        )
        return trace.to_dict()

    def _build_result(self, **kwargs: Any) -> Dict[str, Any]:
        mm = kwargs.pop("migration_modes", self._migration_modes())
        return self._pipeline.results.build_base_result(migration_modes=mm, **kwargs)

    async def _async_simulate(
        self,
        web3_client: Any,
        draft: Mapping[str, Any],
        block_number: int,
        state_overrides: Optional[StateOverride],
    ) -> Dict[str, Any]:
        sim = self._build_sandbox_simulator()
        return cast(
            Dict[str, Any],
            await sim.simulate_async(
                dict(draft),
                async_web3=web3_client,
                block_number=block_number,
                state_overrides=state_overrides,
            ),
        )
