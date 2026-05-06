# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_shadow_policy_schema_normalizes_addresses_and_forbidden_methods() -> None:
    policy = ShadowPolicySchema(
        allowed_target_contracts=["0x0000000000000000000000000000000000000001"],
        forbidden_methods=["0xA9059CBB", " transfer "],
    )
    assert policy.allowed_target_contracts[0] == Web3.to_checksum_address(
        "0x0000000000000000000000000000000000000001"
    )
    assert policy.forbidden_methods == ["0xa9059cbb", "transfer"]


def test_shadow_auditor_blocks_invalid_to_address_under_target_policy() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(
        allowed_target_contracts=["0x0000000000000000000000000000000000000001"],
        forbidden_methods=[],
    )
    with pytest.raises(LirixPolicyViolationException, match="LRX_SHADOW_POLICY_BLOCKED"):
        auditor.audit(
            payload={"to": "not-an-address"}, simulation_result={}, security_policy=policy
        )


def test_shadow_auditor_allows_payload_without_policy_when_simulation_metrics_present() -> None:
    auditor = ShadowAuditor()
    assert (
        auditor.audit(
            payload={"to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001")},
            simulation_result={"metrics": {"slippage_bps": 10}},
        )
        is True
    )
