# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""AGENT_FEEDBACK_REASON_KNOWN ↔ _TAXONOMY_TABLE closure (plan Phase A5)."""

from __future__ import annotations

from lirix.core.canonical_taxonomy import (
    lookup_reason_taxon,
    registered_taxonomy_reason_codes,
    retry_allowed_for_hook_error_code,
)
from lirix.core.constants import (
    _REASON_TO_FAILURE_TYPE,
    AGENT_FEEDBACK_REASON_KNOWN,
    AGENT_FEEDBACK_REASON_TIMEOUT,
    AGENT_FEEDBACK_REASON_UNKNOWN,
    HOOK_ERR_RUNTIME,
    HOOK_ERR_TIMEOUT,
)


def test_agent_feedback_reason_known_matches_taxonomy_table_keys() -> None:
    assert registered_taxonomy_reason_codes() == AGENT_FEEDBACK_REASON_KNOWN


def test_each_known_reason_has_non_unknown_taxon_row() -> None:
    for code in AGENT_FEEDBACK_REASON_KNOWN:
        taxon = lookup_reason_taxon(code)
        assert taxon.reason_code == code


def test_reason_to_failure_type_matches_taxon_default_failure_type() -> None:
    for reason_code, expected_ft in _REASON_TO_FAILURE_TYPE.items():
        taxon = lookup_reason_taxon(reason_code)
        assert taxon.default_failure_type == expected_ft, reason_code


def test_unknown_reason_has_unknown_failure_type() -> None:
    unknown = lookup_reason_taxon(AGENT_FEEDBACK_REASON_UNKNOWN)
    assert unknown.reason_code == AGENT_FEEDBACK_REASON_UNKNOWN


def test_hook_timeout_retry_matches_timeout_taxon() -> None:
    assert (
        retry_allowed_for_hook_error_code(HOOK_ERR_TIMEOUT)
        == lookup_reason_taxon(AGENT_FEEDBACK_REASON_TIMEOUT).retry_allowed
    )


def test_hook_runtime_error_is_not_retryable() -> None:
    assert retry_allowed_for_hook_error_code(HOOK_ERR_RUNTIME) is False
