from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.layers.l5_shadow_auditor import ShadowPolicySchema


def test_shadow_policy_schema_rejects_non_any_non_list_target_contracts() -> None:
    with pytest.raises(ConfigurationGuardException, match="must be 'ANY' or a list"):
        ShadowPolicySchema(allowed_target_contracts="0x0000000000000000000000000000000000000001")


def test_shadow_policy_schema_validates_forbidden_methods_input_types() -> None:
    schema = ShadowPolicySchema(forbidden_methods=None)
    assert schema.forbidden_methods == []

    with pytest.raises(ConfigurationGuardException, match="must be a list"):
        ShadowPolicySchema(forbidden_methods="transfer")

    with pytest.raises(ConfigurationGuardException, match="entries must be strings"):
        ShadowPolicySchema(forbidden_methods=[1234])

    with pytest.raises(ConfigurationGuardException, match="4-byte hex selectors"):
        ShadowPolicySchema(forbidden_methods=["0x1234"])
