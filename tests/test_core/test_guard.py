# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.guard import LirixGuard


def test_test_guard() -> None:
    guard = LirixGuard()
    trace = {
        "outer": "0x1111111111111111111111111111111111111111",
        "nested": ["prefix 0x2222222222222222222222222222222222222222 suffix"],
        "tuple_data": ("0x3333333333333333333333333333333333333333",),
    }
    sanitized = guard.sanitize_trace(trace)
    assert sanitized["outer"] == "0x[SANITIZED]"
    assert sanitized["nested"][0] == "prefix 0x[SANITIZED] suffix"
    assert sanitized["tuple_data"][0] == "0x[SANITIZED]"


def test_test_guard_2() -> None:
    guard = LirixGuard()

    class _AwaitablePayload:
        def __await__(self):
            async def _inner() -> dict[str, str]:
                return {"to": "0x0", "data": "0x"}

            return _inner().__await__()

    with pytest.raises(Exception, match="LRX_SIM_ASYNC_PAYLOAD"):
        guard.parse(_AwaitablePayload())
