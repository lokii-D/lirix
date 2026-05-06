from __future__ import annotations

from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema


def test_shadow_policy_schema_none_targets_defaults_to_any() -> None:
    policy = ShadowPolicySchema(allowed_target_contracts=None)
    assert policy.allowed_target_contracts == "ANY"


def test_shadow_auditor_resolve_policy_applies_default_forbidden_methods() -> None:
    resolved = ShadowAuditor._resolve_policy({"max_slippage_bps": 5})
    assert resolved.max_slippage_bps == 5
    assert "0xa9059cbb" in resolved.forbidden_methods


def test_shadow_auditor_read_metric_supports_flat_metric_dict() -> None:
    assert ShadowAuditor._read_metric({"slippage_bps": 7}, "slippage_bps") == 7  # noqa: SLF001
