# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.constants import (
    HOOK_MULTICALL_PACK,
    HOOK_ON_AUDIT_LOG,
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
    HOOK_RPC_FALLBACK,
    build_agent_resolution,
)


def test_test_constants_build_agent_resolution_minimal_branch_hook_constants() -> None:
    payload = build_agent_resolution(action="repair")
    assert payload == {"action": "repair", "schema_version": 1, "retry": False}
    assert {
        HOOK_PRE_VALIDATE,
        HOOK_POST_VALIDATE,
        HOOK_PRE_SIMULATION,
        HOOK_POST_SIMULATION,
        HOOK_ON_AUDIT_LOG,
        HOOK_RPC_FALLBACK,
        HOOK_MULTICALL_PACK,
    }
