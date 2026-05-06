# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_auditor_allows_valid_payload_with_any_target_policy() -> None:
    auditor = ShadowAuditor()
    assert (
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "noop",
            },
            simulation_result={"metrics": {"slippage_bps": 1}},
            security_policy=ShadowPolicySchema(
                allowed_target_contracts="ANY", forbidden_methods=[]
            ),
        )
        is True
    )
