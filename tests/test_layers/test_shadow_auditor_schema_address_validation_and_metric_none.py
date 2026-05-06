from __future__ import annotations

import pytest
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema


def test_shadow_policy_schema_rejects_invalid_target_address() -> None:
    with pytest.raises(ValueError, match="invalid address"):
        ShadowPolicySchema(allowed_target_contracts=["not-an-address"])


def test_shadow_auditor_read_metric_returns_none_for_missing_values() -> None:
    assert ShadowAuditor._read_metric({"metrics": {"other": 1}}, "slippage_bps") is None
    assert ShadowAuditor._read_metric({"slippage_bps": None}, "slippage_bps") is None
