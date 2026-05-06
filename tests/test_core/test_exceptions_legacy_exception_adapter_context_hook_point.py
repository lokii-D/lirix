# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.exceptions import LirixBaseException


def test_test_exceptions_legacy_exception_adapter_context_hook_point() -> None:
    exc = LirixBaseException(
        resolution_agent="agent",
        resolution_dev="dev",
        value_protected="vp",
        context={"k": 1},
        hook_point="hook",
    )
    assert exc.to_dict()["resolution_for_agent"] == "agent"
    assert exc.to_dict()["resolution_for_developer"] == "dev"
    assert exc.context == {"k": 1}
    assert exc.hook_point == "hook"


def test_test_exceptions_legacy_exception_adapter_context_hook_point_2() -> None:
    exc = LirixBaseException(human_readable_reason="legacy", context=[1, 2])
    assert exc.context == {"raw_context": [1, 2]}
    assert "legacy" in str(exc)
