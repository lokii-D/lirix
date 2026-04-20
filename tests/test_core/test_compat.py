# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import List

import lirix.core.compat as compat


def test_compat_get_origin_and_args() -> None:
    assert compat.get_origin(List[int]) is list
    assert int in compat.get_args(List[int])


def test_compat_get_type_hints() -> None:
    def f(x: int) -> str:
        return str(x)

    hints = compat.get_type_hints(f)
    assert hints["x"] is int
    assert hints["return"] is str
