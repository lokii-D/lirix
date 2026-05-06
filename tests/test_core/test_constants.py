# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.constants import PREDEFINED_HOOK_POINTS, build_agent_resolution


def test_test_constants() -> None:
    payload = build_agent_resolution(
        action="repair",
        target_field="rpc_urls",
        retry=True,
        hook_point="pre_validate",
        notes="retry after fix",
        extra_flag=1,
    )
    assert payload["action"] == "repair"
    assert payload["schema_version"] == 1
    assert payload["target_field"] == "rpc_urls"
    assert payload["retry"] is True
    assert payload["hook_point"] == "pre_validate"
    assert payload["notes"] == "retry after fix"
    assert payload["extra_flag"] == 1
    assert "pre_validate" in PREDEFINED_HOOK_POINTS
