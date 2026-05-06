# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix.core.guard import LirixGuard


def test_test_guard_guard_sync_path_builds_sanitizes_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    guard = LirixGuard(rpc_url="http://example.invalid")

    class _Sim:
        async def async_run_simulation(
            self, target: str, calldata: str, sender: Any = None, value: int = 0
        ) -> bool:
            return True

    monkeypatch.setattr(guard, "_simulator", _Sim())
    monkeypatch.setattr(guard._builder, "build", lambda sig, args: "0xdeadbeef")
    monkeypatch.setattr(guard._schema_validator, "validate", lambda draft: True)
    assert (
        asyncio.run(
            guard._parse_impl(
                {
                    "to": "0x0000000000000000000000000000000000000001",
                    "function_signature": "ping()",
                    "data": "0x",
                    "assertions": [],
                }
            )
        )
        is True
    )


def test_test_guard_guard_sync_path_builds_sanitizes_trace_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = LirixGuard(rpc_url="http://example.invalid")
    monkeypatch.setattr(guard._schema_validator, "validate", lambda draft: True)
    with pytest.raises(Exception, match="LRX_SIM_TARGET_REQUIRED"):
        asyncio.run(guard._parse_impl({"data": "0x", "function_signature": "ping()"}))
