# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_test_shadow_auditor() -> None:
    auditor = ShadowAuditor()
    payload = {
        "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
        "function_name": "transfer",
        "data": "0xa9059cbb" + "00" * 64,
    }
    with pytest.raises(Exception, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(payload=payload, simulation_result={"slippage_bps": 1})


def test_test_shadow_auditor_2() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(
        max_slippage_bps=50,
        allowed_target_contracts=[
            Web3.to_checksum_address("0x0000000000000000000000000000000000000002")
        ],
        forbidden_methods=[],
    )
    with pytest.raises(Exception, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "swapExactTokensForTokens",
                "data": "0x38ed1739",
            },
            simulation_result={"slippage_bps": 1},
            security_policy=policy,
        )
