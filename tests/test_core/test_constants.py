# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.constants import PREDEFINED_HOOK_POINTS, build_agent_resolution


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("action", "repair"),
        ("target_field", "rpc_urls"),
        ("hook_point", "pre_validate"),
        ("notes", "retry after fix"),
        ("extra_flag", 1),
    ],
)
def test_build_agent_resolution_fields(field: str, expected: object) -> None:
    payload = build_agent_resolution(
        action="repair",
        target_field="rpc_urls",
        retry=True,
        hook_point="pre_validate",
        notes="retry after fix",
        extra_flag=1,
    )
    assert payload[field] == expected


def test_build_agent_resolution_schema_and_hook_points_contract() -> None:
    payload = build_agent_resolution(
        action="repair",
        target_field="rpc_urls",
        retry=True,
        hook_point="pre_validate",
    )
    assert payload["schema_version"] == 1
    assert payload["retry"] is True
    assert "pre_validate" in PREDEFINED_HOOK_POINTS
