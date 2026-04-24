# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.exceptions import LirixBaseException, LirixSecurityException


def test_lirix_base_exception_json_contract() -> None:
    exc = LirixBaseException(
        error_code="LRX_UNIT_TEST",
        value_protected="Vault",
        resolution_agent="agent resolution",
        resolution_dev="developer resolution",
    )

    payload = exc.to_dict()

    assert set(payload) == {
        "error_code",
        "resolution_for_agent",
        "resolution_for_developer",
        "value_protected",
    }
    assert payload["error_code"] == "LRX_UNIT_TEST"
    assert payload["resolution_for_agent"] == "agent resolution"
    assert payload["resolution_for_developer"] == "developer resolution"
    assert payload["value_protected"] == "Vault"


def test_legacy_adapter_kwargs() -> None:
    exc = LirixSecurityException(human_readable_reason="old")

    payload = exc.to_dict()

    assert payload["resolution_for_agent"] == "old"
