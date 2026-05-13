# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3


def test_test_shadow_auditor_shadow_policy_schema_rejects_boolean_malformed_methods() -> None:
    with pytest.raises(ConfigurationGuardException, match="must be 'ANY' or a list"):
        ShadowPolicySchema(allowed_target_contracts=True)
    with pytest.raises(ConfigurationGuardException, match="non-empty strings"):
        ShadowPolicySchema(forbidden_methods=["   "])


def test_test_shadow_auditor_shadow_policy_schema_rejects_boolean_malformed_methods_2() -> None:
    auditor = ShadowAuditor()
    policy = ShadowPolicySchema(allowed_target_contracts="ANY", forbidden_methods=[])
    assert (
        auditor.audit(
            payload={
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000002"),
                "function_name": "swap",
                "data": "0x12345678",
            },
            simulation_result={},
            security_policy=policy,
        )
        is True
    )


def test_test_shadow_auditor_shadow_policy_schema_rejects_boolean_malformed_methods_3() -> None:
    assert ShadowAuditor._DEFAULT_POLICY.max_slippage_bps == 50
