from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_policy_schema_rejects_non_hex_forbidden_selector() -> None:
    with pytest.raises(ValueError):
        ShadowPolicySchema(forbidden_methods=["0xzzzzzzzz"])


def test_shadow_auditor_blocks_trimmed_function_name_when_forbidden() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(
        allowed_target_contracts="ANY",
        forbidden_methods=["transfer"],
        max_slippage_bps=None,
    )
    with pytest.raises(LirixPolicyViolationException, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "  transfer  ",
                "data": "0x",
            },
            simulation_result={},
            security_policy=policy,
        )
