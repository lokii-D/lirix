# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_hex_to_bytes_whitespace_invalid_prefix() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._hex_to_bytes(" 0x1234 ") == b"\x124"
    assert engine._hex_to_bytes("   1234") is None
