# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_auditor_blocks_disallowed_target_then_forbidden_method() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(
        allowed_target_contracts=["0x0000000000000000000000000000000000000001"],
        forbidden_methods=["0xdeadbeef", "mint"],
    )
    with pytest.raises(LirixPolicyViolationException) as exc:
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000002"),
                "data": "0x1234",
            },
            simulation_result={"return_data": "0x0", "metrics": {"slippage_bps": 1}},
            security_policy=policy,
        )
    assert exc.value.context["policy_key"] == "allowed_target_contracts"
    with pytest.raises(LirixPolicyViolationException) as exc:
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "data": "0xdeadbeef",
            },
            simulation_result={"return_data": "0x0", "metrics": {"slippage_bps": 1}},
            security_policy=policy,
        )
    assert exc.value.context["policy_key"] == "forbidden_methods"
