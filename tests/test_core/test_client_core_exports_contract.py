from __future__ import annotations

import lirix._client_core as client_core


def test_client_core_exports_are_minimized_for_compatibility_only() -> None:
    expected = {
        "Lirix",
        "build_for_chain_profile",
        "register_hook",
        "replay_session",
        "resolve_failure_protocol",
        "verify_replay_bundle",
    }
    assert set(client_core.__all__) == expected
    assert len(client_core.__all__) == len(set(client_core.__all__))


def test_client_core_does_not_re_expand_surface_with_high_risk_names() -> None:
    # This contract prevents accidental expansion of the internal compat surface.
    # A small number of "patch points" are permitted for tests/tools, but everything else should
    # remain private unless explicitly contracted.
    allowed_patch_points = {
        "IntentValidator",
        "SchemaValidator",
        "DeFiPayloadParser",
        "RPCManager",
        "SandboxSimulator",
        "HookManager",
        "rejected_step_to_agent_feedback",
    }
    publicish = {name for name in dir(client_core) if not name.startswith("_")}
    # Allow the explicitly contracted surface only.
    publicish -= set(client_core.__all__)
    # Permit a small set of expected module metadata.
    publicish -= {"annotations", "os", "warnings"}
    assert publicish <= allowed_patch_points
