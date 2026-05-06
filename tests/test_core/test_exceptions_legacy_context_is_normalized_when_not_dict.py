# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.exceptions import LirixBaseException


def test_test_exceptions_legacy_context_is_normalized_when_not_dict() -> None:
    exc = LirixBaseException(context=["raw", "list"])
    payload = exc.to_dict()
    assert payload["error_code"] == "LRX_LEGACY_ERROR"
    assert exc.context == {"raw_context": ["raw", "list"]}


def test_test_exceptions_legacy_context_is_normalized_when_not_dict_2() -> None:
    exc = LirixBaseException(human_readable_reason="reason", hook_point="hook")
    assert exc.resolution_for_agent == "reason"
    assert exc.resolution_for_developer == "hook"
