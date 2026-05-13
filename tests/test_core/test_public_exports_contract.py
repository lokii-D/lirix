from __future__ import annotations

import lirix
import lirix.core as core
import lirix.layers as layers

# Must match root public symbol membership of ``lirix.__all__`` (see ``lirix/__init__.py``).
_EXPECTED_ROOT_EXPORTS: tuple[str, ...] = (
    "Lirix",
    "LirixConfig",
    "LirixSecurityException",
    "HookManager",
    "PipelineLayerExecutor",
    "RpcEvidenceSource",
    "SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR",
    "ProxyPiercer",
    "RPCManager",
    "SandboxSimulator",
    "atomic_multicall",
    "build_for_chain_profile",
    "register_hook",
    "replay_session",
    "resolve_failure_protocol",
    "verify_replay_bundle",
)
_MAX_CORE_EXPORT_COUNT = 28


def test_root_package_exports_contract() -> None:
    """Authoritative root ``__all__`` contract.

    Migration narrative: **`docs/migration_legacy_to_v2.md`** (§ Root export policy).
    """
    assert set(lirix.__all__) == set(_EXPECTED_ROOT_EXPORTS)
    assert len(lirix.__all__) == len(set(lirix.__all__))


def test_root_package_does_not_export_client_pipeline_protocol() -> None:
    """``ClientPipelineProtocol`` is an internal composition surface (``client_components``), not root API."""
    assert "ClientPipelineProtocol" not in lirix.__all__
    assert not hasattr(lirix, "ClientPipelineProtocol")


def test_core_exports_include_canonical_utilities() -> None:
    expected = {
        "LirixConfig",
        "resolve_config",
        "HookManager",
        "HookDecision",
        "HookPatch",
        "HookAnnotation",
        "ReadonlyHookPayload",
        "HOOK_PRE_VALIDATE",
        "HOOK_PRE_SIMULATION",
        "HOOK_POST_VALIDATE",
        "HOOK_POST_SIMULATION",
        "HookExecutionException",
        "MulticallEncoder",
        "PipelineLayerExecutor",
        "RpcEvidenceSource",
        "canonicalize_error_code",
        "canonicalize_reason_code",
        "canonicalize_failure_type",
        "build_agent_resolution",
        "build_failure_protocol",
        "build_failure_protocol_from_agent_feedback",
        "resolve_failure_protocol_to_agent_feedback",
        "ExecutionEvidence",
        "PolicyDecision",
        "ExecutionPlan",
        "ValidationSession",
        "LirixSecurityException",
        "verify_replay_bundle",
    }
    assert set(core.__all__) == expected
    assert len(core.__all__) == len(set(core.__all__))


def test_core_exports_size_is_bounded_to_prevent_surface_bloat() -> None:
    assert len(core.__all__) <= _MAX_CORE_EXPORT_COUNT


def test_layers_exports_remain_stable_for_runtime_pipeline() -> None:
    expected = {
        "IntentValidator",
        "SchemaValidator",
        "DeFiPayloadParser",
        "RPCManager",
        "SandboxSimulator",
        "ShadowAuditor",
    }
    assert expected.issubset(set(layers.__all__))
    assert len(layers.__all__) == len(set(layers.__all__))
