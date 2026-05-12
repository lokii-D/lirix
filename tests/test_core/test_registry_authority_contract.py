from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.registry_authority import (
    assert_registry_authority_contract,
    registry_authority_snapshot,
)


def test_registry_authority_snapshot_contains_digest_and_schema() -> None:
    payload = registry_authority_snapshot(chain_registry={"a": 1}, decoder_registry={"b": 2})
    assert payload["schema_version"] == "1.0"
    assert isinstance(payload.get("authority_digest"), str)
    assert len(payload["authority_digest"]) == 64


def test_registry_authority_contract_rejects_digest_mismatch() -> None:
    payload = registry_authority_snapshot(chain_registry={"a": 1}, decoder_registry={"b": 2})
    payload["authority_digest"] = "0" * 64
    with pytest.raises(ConfigurationGuardException) as exc_info:
        assert_registry_authority_contract(payload)
    assert exc_info.value.context.get("reason") == "registry_authority_digest_mismatch"


def test_registry_authority_contract_accepts_schema_minor_upgrade_in_1x() -> None:
    payload = registry_authority_snapshot(chain_registry={"a": 1}, decoder_registry={"b": 2})
    payload["schema_version"] = "1.1"
    from lirix.core.registry_authority import _sha256_payload

    payload["authority_digest"] = _sha256_payload(
        {k: v for k, v in payload.items() if k != "authority_digest"}
    )
    verified = assert_registry_authority_contract(payload)
    assert verified["schema_version"] == "1.1"


def test_registry_authority_contract_rejects_schema_major_upgrade() -> None:
    payload = registry_authority_snapshot(chain_registry={"a": 1}, decoder_registry={"b": 2})
    payload["schema_version"] = "2.0"
    from lirix.core.registry_authority import _sha256_payload

    payload["authority_digest"] = _sha256_payload(
        {k: v for k, v in payload.items() if k != "authority_digest"}
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        assert_registry_authority_contract(payload)
    assert exc_info.value.context.get("reason") == "registry_authority_schema_mismatch"
