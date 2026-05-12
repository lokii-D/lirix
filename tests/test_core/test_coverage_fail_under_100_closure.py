# SPDX-License-Identifier: MIT
"""Branch and module coverage to satisfy ``fail_under=100`` on ``lirix/``."""

from __future__ import annotations

import hashlib
import json
from collections import UserDict
from types import MappingProxyType, SimpleNamespace
from typing import Any, cast

import pytest
from lirix import Lirix
from lirix.core import client_components as cc
from lirix.core import pipeline_protocol as pp
from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config
from lirix.core.config_governance import GovernanceConfig, validate_governance_modes
from lirix.core.constants import normalize_policy_lifecycle_mode
from lirix.core.exceptions import (
    ConfigurationGuardException,
    LirixBaseException,
    LirixPolicyViolationException,
)
from lirix.core.orchestrator import LirixPipelineOrchestrator
from lirix.core.session import ValidationSession
from lirix.layers.l5_shadow_auditor import (
    PolicyBundle,
    PolicyVersion,
    ShadowAuditor,
    ShadowPolicySchema,
)


def _policy_integrity_digest(policy: ShadowPolicySchema) -> str:
    canonical = json.dumps(
        policy.model_dump(mode="python"),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_pipeline_protocol_shim_reexports_client_components() -> None:
    assert pp.RequestContext is cc.RequestContext
    assert pp.request_normalization is cc.request_normalization
    assert pp.error_to_feedback_mapper is cc.error_to_feedback_mapper
    assert pp.pipeline_orchestrator is cc.pipeline_orchestrator
    assert pp.result_envelope_builder is cc.result_envelope_builder
    assert set(pp.__all__) == {
        "RequestContext",
        "error_to_feedback_mapper",
        "pipeline_orchestrator",
        "request_normalization",
        "result_envelope_builder",
    }


def test_error_to_feedback_mapper_non_dict_context() -> None:
    class _E:
        context = "not-a-dict"

    assert cc.error_to_feedback_mapper(_E()) == {"raw": "not-a-dict"}


def test_simulation_payload_branches() -> None:
    out = {"simulation_ok": True, "block_number": 1}
    no_val = LirixPipelineOrchestrator._simulation_payload(out, validated=False)
    assert "validated" not in no_val
    with_policy = LirixPipelineOrchestrator._simulation_payload(
        out,
        validated=False,
        policy_decision={"decision": "allow"},
    )
    assert with_policy["policy_decision"] == {"decision": "allow"}


def test_normalize_policy_lifecycle_mode_non_deprecated_passthrough() -> None:
    assert normalize_policy_lifecycle_mode("digest_verified") == "digest_verified"


def test_normalize_policy_lifecycle_mode_signed_only_maps() -> None:
    assert normalize_policy_lifecycle_mode("signed_only") == "digest_verified"


def test_core_guard_module_removed() -> None:
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("lirix.core.guard")


def test_validate_governance_strict_rpc_evidence_not_v2_only_raises() -> None:
    cfg = cast(
        GovernanceConfig,
        SimpleNamespace(
            strict_mode=True,
            blacklisted_addresses=[],
            whitelisted_addresses=[],
            allowed_to_addresses=[],
            rpc_evidence_mode="legacy",
            policy_lifecycle_mode="digest_verified",
            decoder_plugins=[],
            chain_profile={},
            hook_contract_mode="legacy",
            runtime_patch_allowlist=[],
            l4_min_success_count=None,
            l4_min_success_ratio=None,
        ),
    )
    with pytest.raises(ConfigurationGuardException) as exc:
        validate_governance_modes(cfg)
    assert exc.value.context.get("reason") == "rpc_evidence_mode_single_stack_required"


def test_lirix_config_fallback_revalidates_when_profile_fills_defaults() -> None:
    """Exercise ``Lirix.__init__`` path where chain_profile-derived defaults patch explicit fields."""
    mc = "0xcA11bde05977b3631167028862bE2a173976CA11"
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://example.invalid"],
        multicall3_address=None,
        uniswap_v2_router=None,
        chain_profile={"multicall3_address": mc},
    )
    guard = Lirix(config=cfg)
    assert guard.config.multicall3_address == mc


def test_lirix_revalidates_when_chain_profile_provides_default_value() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        multicall3_address=None,
        chain_profile={"multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11"},
    )
    guard = Lirix(config=cfg)
    assert guard.config.multicall3_address == "0xcA11bde05977b3631167028862bE2a173976CA11"


def test_resolve_config_runtime_patch_skips_none_values() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=False,
        runtime_patch_allowlist=["allowed_intents"],
    )
    resolved, _tags = resolve_config(
        config=cfg,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["z"], "ignored_none_field": None},
    )
    assert resolved.allowed_intents == ["z"]


def test_resolve_config_explicit_chain_profile_none_via_runtime_preserves_sentinel() -> None:
    inner = LirixConfig(chain_id=1, rpc_urls=[], chain_profile=None)
    resolved, tags = resolve_config(
        config=inner,
        rpc_urls=None,
        runtime_patch={"chain_profile": None},
    )
    assert resolved.chain_profile is None
    assert tags.get("chain_profile") == "runtime"


def test_resolve_config_inferred_chain_profile_runtime_none_special_case() -> None:
    resolved, tags = resolve_config(config=None, rpc_urls=[], runtime_patch={"chain_profile": None})
    assert resolved.chain_profile is None
    assert tags.get("chain_profile") == "runtime"


def test_result_builder_optional_top_level_payload_aliases_and_audit_governance() -> None:
    rb = cc.ResultBuilder()
    base_kw: dict[str, Any] = {
        "status": "approved",
        "decision": "approved",
        "agent_feedback": {},
        "validation_session": {},
        "replay_bundle": {},
        "forensic_bundle": {},
        "security_trace": {},
        "evidence_schema_version": "1.0",
        "evidence_v2": {},
        "migration_modes": {},
        "payload": {
            "validated": False,
            "simulation_ok": True,
            "simulation_outcome": {},
            "policy_decision": {"x": 1},
        },
        "audit": {"a": 1},
        "governance": {"g": 1},
    }
    out = rb.build_base_result(**base_kw)
    assert out["simulation_ok"] is True
    assert out["audit"] == {"a": 1}
    assert out["governance"] == {"g": 1}


def test_result_builder_audit_without_payload_duplicates_top_level_fields() -> None:
    rb = cc.ResultBuilder()
    out = rb.build_base_result(
        status="approved",
        decision="approved",
        agent_feedback={},
        validation_session={},
        replay_bundle={},
        forensic_bundle={},
        security_trace={},
        evidence_schema_version="1.0",
        evidence_v2={},
        migration_modes={},
        payload=None,
        audit={"simulation_ok": True},
        governance={"mode": "digest_verified"},
    )
    assert out["audit"]["simulation_ok"] is True
    assert out["governance"]["mode"] == "digest_verified"


def test_result_builder_governance_without_audit() -> None:
    rb = cc.ResultBuilder()
    out = rb.build_base_result(
        status="approved",
        decision="approved",
        agent_feedback={},
        validation_session={},
        replay_bundle={},
        forensic_bundle={},
        security_trace={},
        evidence_schema_version="1.0",
        evidence_v2={},
        migration_modes={},
        payload=None,
        audit=None,
        governance={"k": "v"},
    )
    assert out["governance"] == {"k": "v"}
    assert "audit" not in out


def test_result_builder_audit_without_governance() -> None:
    rb = cc.ResultBuilder()
    out = rb.build_base_result(
        status="approved",
        decision="approved",
        agent_feedback={},
        validation_session={},
        replay_bundle={},
        forensic_bundle={},
        security_trace={},
        evidence_schema_version="1.0",
        evidence_v2={},
        migration_modes={},
        payload=None,
        audit={"x": 1},
        governance=None,
    )
    assert out["audit"] == {"x": 1}
    assert "governance" not in out


def test_shadow_auditor_policy_bundle_import_export_mapping_branch() -> None:
    auditor = ShadowAuditor()
    mapping_bundle = {"bundle_id": "cov-bundle", "versions": [], "active_version": None}
    dumped = auditor.export_policy_bundle(mapping_bundle)
    roundtrip = auditor.export_policy_bundle(
        dict(auditor.import_policy_bundle(dumped).model_dump(mode="python"))
    )
    assert roundtrip["bundle_id"] == "cov-bundle"


def test_shadow_auditor_rejects_inactive_selected_version_under_integrity() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    inactive = PolicyVersion(
        version="v1",
        environment="default",
        status="draft",
        policy=ShadowAuditor._DEFAULT_POLICY,
    )
    bundle = PolicyBundle(bundle_id="inactive-bundle", versions=[inactive])
    with pytest.raises(LirixPolicyViolationException):
        auditor._resolve_policy_with_report({"policy_bundle": bundle.model_dump(mode="python")})


def test_shadow_auditor_legacy_lifecycle_skips_integrity_enforcement_block() -> None:
    auditor = ShadowAuditor(lifecycle_mode="legacy")
    draft = PolicyVersion(
        version="v1",
        environment="default",
        status="draft",
        policy=ShadowAuditor._DEFAULT_POLICY,
    )
    bundle = PolicyBundle(bundle_id="legacy-lifecycle", versions=[draft])
    policy, _report = auditor._resolve_policy_with_report(
        {"policy_bundle": bundle.model_dump(mode="python")},
        lifecycle_mode=auditor._effective_lifecycle_mode(),
    )
    assert isinstance(policy, ShadowPolicySchema)


def test_shadow_auditor_select_bundle_active_pointer_ignored_when_env_mismatched() -> None:
    staging = PolicyVersion(
        version="v2", environment="staging", policy=ShadowAuditor._DEFAULT_POLICY
    )
    prod = PolicyVersion(version="v1", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    bundle = PolicyBundle(
        bundle_id="env-mismatch-active", versions=[staging, prod], active_version="v2"
    )
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version=None,
    )
    assert chosen.version == "v1"


def test_shadow_auditor_rejects_bad_integrity_digest_when_active() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    pv = PolicyVersion(
        version="v1",
        environment="default",
        status="active",
        policy=ShadowAuditor._DEFAULT_POLICY,
        integrity_digest="not-a-real-digest",
    )
    bundle = PolicyBundle(bundle_id="bad-int", versions=[pv])
    with pytest.raises(LirixPolicyViolationException):
        auditor._resolve_policy_with_report({"policy_bundle": bundle.model_dump(mode="python")})


def test_shadow_auditor_select_bundle_version_prefers_requested_version() -> None:
    v2 = PolicyVersion(version="v2", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    v1 = PolicyVersion(version="v1", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    bundle = PolicyBundle(bundle_id="multi", versions=[v2, v1])
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version="v1",
    )
    assert chosen.version == "v1"


def test_shadow_auditor_select_bundle_version_unknown_preferred_falls_through() -> None:
    v2 = PolicyVersion(version="v2", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    v1 = PolicyVersion(version="v1", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    bundle = PolicyBundle(bundle_id="pf", versions=[v2, v1], active_version=None)
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version="does-not-exist",
    )
    assert chosen.version == "v2"


def test_shadow_auditor_select_bundle_version_falls_back_to_active_field() -> None:
    v2 = PolicyVersion(version="v2", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    v1 = PolicyVersion(version="v1", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    bundle = PolicyBundle(bundle_id="multi", versions=[v1, v2], active_version="v2")
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version=None,
    )
    assert chosen.version == "v2"


def test_shadow_auditor_select_bundle_version_first_env_match() -> None:
    wrong_env = PolicyVersion(
        version="v9", environment="staging", policy=ShadowAuditor._DEFAULT_POLICY
    )
    prod = PolicyVersion(version="v1", environment="prod", policy=ShadowAuditor._DEFAULT_POLICY)
    bundle = PolicyBundle(bundle_id="envpick", versions=[wrong_env, prod], active_version=None)
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version=None,
    )
    assert chosen.version == "v1"


def test_shadow_auditor_select_bundle_version_defaults_to_first_when_no_env_match() -> None:
    only = PolicyVersion(
        version="vonly", environment="staging", policy=ShadowAuditor._DEFAULT_POLICY
    )
    bundle = PolicyBundle(bundle_id="fallback-first", versions=[only])
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version=None,
    )
    assert chosen.version == "vonly"


def test_shadow_auditor_bundle_rollback_replaces_non_active_selected_version() -> None:
    auditor = ShadowAuditor(lifecycle_mode="digest_verified")
    base_policy = ShadowAuditor._DEFAULT_POLICY
    digest = _policy_integrity_digest(base_policy)
    deprecated = PolicyVersion(
        version="v2",
        environment="default",
        status="deprecated",
        rollback_to="v1",
        policy=base_policy,
    )
    stable = PolicyVersion(
        version="v1",
        environment="default",
        status="active",
        policy=base_policy,
        integrity_digest=digest,
    )
    bundle = PolicyBundle(
        bundle_id="rollback-case", versions=[deprecated, stable], active_version="v2"
    )
    _policy, report = auditor._resolve_policy_with_report(
        {"policy_bundle": bundle.model_dump(mode="python")}
    )
    assert report.get("rollback_applied") is True


def test_shadow_auditor_select_bundle_version_empty_versions_returns_default() -> None:
    bundle = PolicyBundle(bundle_id="empty", versions=[], active_version=None)
    chosen = ShadowAuditor._select_bundle_version(
        bundle=bundle,
        environment="prod",
        preferred_version=None,
    )
    assert chosen.version == "default"
    assert chosen.environment == "default"


def test_shadow_auditor_verify_policy_integrity_false_when_digest_missing() -> None:
    pv = PolicyVersion(
        version="v1",
        environment="default",
        policy=ShadowAuditor._DEFAULT_POLICY,
        integrity_digest=None,
        signature=None,
    )
    assert ShadowAuditor._verify_policy_integrity(pv) is False


def test_forensic_bundle_decision_backfill_reversed_timeline_scan() -> None:
    """Cover reversed ``session_event`` decision scan when no layer/context hook summary landed."""
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {"details": {"context": {"reason": "orphan_only"}}},
        }
    )
    _ = sess.forensic_bundle()


def test_forensic_bundle_skips_non_dict_payload_on_rejected_decision() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": MappingProxyType({"details": {"context": {"reason": "x"}}}),
        }
    )
    _ = sess.forensic_bundle()


def test_forensic_bundle_hook_result_non_mapping_skips_fatal_summary() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {
                "details": {
                    "context": {
                        "layer": "hooks",
                        "reason": "x",
                        "hook_result": "not-a-mapping",
                    }
                }
            },
        }
    )
    assert sess.forensic_bundle().get("fatal_hook_summary") is None


def test_forensic_bundle_reversed_scan_skips_non_dict_timeline_wrappers() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        UserDict(
            {
                "kind": "session_event",
                "event_type": "decision",
                "status": "rejected",
                "payload": {"details": {}},
            }
        )
    )
    _ = sess.forensic_bundle()


def test_forensic_bundle_reversed_skips_non_dict_details_and_context() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {"details": "not-a-dict"},
        }
    )
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {"details": {"context": "not-a-mapping"}},
        }
    )
    _ = sess.forensic_bundle()


def test_forensic_bundle_second_context_skips_fatal_hook_re_extract() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {
                "details": {
                    "context": {
                        "layer": "hooks",
                        "hook_result": {
                            "failure_level": "fatal",
                            "hook_point": "first",
                            "error_code": "E1",
                            "error_type": "t",
                        },
                    }
                }
            },
        }
    )
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {
                "details": {
                    "context": {
                        "layer": "hooks",
                        "hook_result": {
                            "failure_level": "soft",
                            "hook_point": "second",
                            "error_code": "E2",
                            "error_type": "t",
                        },
                    }
                }
            },
        }
    )
    fb = sess.forensic_bundle()
    assert fb.get("fatal_hook_summary", {}).get("hook_point") == "first"


def test_forensic_bundle_reversed_skips_mapping_details_that_are_not_dicts() -> None:
    sess = ValidationSession()
    sess.timeline.append(
        {
            "kind": "session_event",
            "event_type": "decision",
            "status": "rejected",
            "payload": {"details": MappingProxyType({"context": {}})},
        }
    )
    _ = sess.forensic_bundle()


async def test_async_validate_only_lirix_base_exception_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])

    def _boom(*_a: Any, **_k: Any) -> None:
        raise LirixBaseException(
            error_code="cov_async_validate_only",
            resolution_agent="no",
            value_protected="0",
            context={"layer": "L2", "reason": "schema_invalid"},
        )

    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", _boom)
    with pytest.raises(LirixBaseException):
        await guard.async_validate_only("swap", {"to": "0x1", "data": "0x"})


def _install_min_client_success_patches(monkeypatch: pytest.MonkeyPatch) -> Lirix:
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        },
    )

    async def _simulate_async(self, payload, async_web3, block_number, state_overrides=None):  # type: ignore[no-untyped-def]
        return {
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)
    return Lirix(rpc_urls=["https://example.invalid"])


async def test_async_validate_only_external_session_skips_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _install_min_client_success_patches(monkeypatch)
    sess = ValidationSession()
    out = await guard.async_validate_only("swap", {"to": "0x1", "data": "0x"}, session=sess)
    assert out["decision"] == "approved"


async def test_async_simulate_only_external_session_skips_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = _install_min_client_success_patches(monkeypatch)
    sess = ValidationSession()
    out = await guard.async_simulate_only({"to": "0x1", "data": "0x"}, session=sess)
    assert out["decision"] == "approved"


async def test_async_simulate_only_lirix_base_exception_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _boom(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        raise LirixBaseException(
            error_code="cov_async_sim",
            resolution_agent="no",
            value_protected="0",
            context={"layer": "L5", "reason": "sim_failed"},
        )

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _boom)
    with pytest.raises(LirixBaseException):
        await guard.async_simulate_only({"to": "0x1", "data": "0x"})
