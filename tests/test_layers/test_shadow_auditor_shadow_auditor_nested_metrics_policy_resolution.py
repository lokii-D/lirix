# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_test_shadow_auditor_shadow_auditor_nested_metrics_policy_resolution() -> None:
    auditor = ShadowAuditor()
    policy = {"max_slippage_bps": 100, "allowed_target_contracts": "ANY", "forbidden_methods": []}
    assert (
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "swap",
            },
            simulation_result={"metrics": {"slippage_bps": 5}},
            security_policy=policy,
        )
        is True
    )


def test_test_shadow_auditor_shadow_auditor_nested_metrics_policy_resolution_2() -> None:
    schema = ShadowPolicySchema(
        max_slippage_bps=10,
        allowed_target_contracts=["0x0000000000000000000000000000000000000001"],
        forbidden_methods=[" swap ", "0x38ed1739"],
    )
    assert schema.allowed_target_contracts != "ANY"
    assert schema.forbidden_methods == ["swap", "0x38ed1739"]
