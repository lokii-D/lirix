# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_mantle_default_policy_keeps_low_slippage_swap_allowed() -> None:
    auditor = ShadowAuditor()
    payload = {
        "to": Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a"),
        "function_name": "swap",
        "data": "0xd004f0f8" + "00" * 64,
    }
    assert auditor.audit(payload=payload, simulation_result={"slippage_bps": 12}) is True


def test_mantle_policy_blocks_high_slippage_even_with_nested_metrics() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(max_slippage_bps=50)
    with pytest.raises(Exception, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a"),
                "function_name": "swap",
                "data": "0xd004f0f8" + "00" * 64,
            },
            simulation_result={"metrics": {"slippage_bps": 75}},
            security_policy=policy,
        )


def test_mantle_policy_blocks_specific_target_outside_allowlist() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(
        allowed_target_contracts=[Web3.to_checksum_address("0x0000000000000000000000000000000000000002")],
        forbidden_methods=[],
    )
    with pytest.raises(Exception, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a"),
                "function_name": "swap",
                "data": "0xd004f0f8" + "00" * 64,
            },
            simulation_result={"slippage_bps": 1},
            security_policy=policy,
        )
