# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_auditor_blocks_forbidden_function_name_with_whitespace() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(forbidden_methods=["swapExactTokensForTokens"])

    with pytest.raises(Exception, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "  swapExactTokensForTokens  ",
                "data": "0xdeadbeef",
            },
            simulation_result={"slippage_bps": 1},
            security_policy=policy,
        )


def test_shadow_auditor_policy_merge_accepts_mapping_overrides() -> None:
    auditor = ShadowAuditor()

    assert (
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "function_name": "swap",
                "data": "0xdeadbeef",
            },
            simulation_result={"metrics": {"slippage_bps": 25}},
            security_policy={"max_slippage_bps": 30, "forbidden_methods": []},
        )
        is True
    )


def test_shadow_policy_schema_rejects_invalid_forbidden_selector_length() -> None:
    with pytest.raises(
        ConfigurationGuardException,
        match="4-byte hex selectors",
    ):
        ShadowPolicySchema(forbidden_methods=["0x1234"])
