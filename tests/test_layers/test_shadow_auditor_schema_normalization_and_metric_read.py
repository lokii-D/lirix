# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_policy_schema_trims_methods_and_read_metric_supports_nested_metrics() -> None:
    schema = ShadowPolicySchema(
        allowed_target_contracts=["0x0000000000000000000000000000000000000001"],
        forbidden_methods=[" swapExactTokensForTokens ", "0x12345678"],
    )
    assert schema.allowed_target_contracts == [
        Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    ]
    assert schema.forbidden_methods == ["swapExactTokensForTokens", "0x12345678"]
    assert ShadowAuditor._read_metric({"metrics": {"slippage_bps": 3}}, "slippage_bps") == 3
