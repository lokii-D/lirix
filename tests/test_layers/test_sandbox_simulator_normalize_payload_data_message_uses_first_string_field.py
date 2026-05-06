# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_normalize_payload_data_message_uses_first_string_field() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._normalize_payload({"message": "0x1234", "data": 123}) == b"\x124"
    assert engine._normalize_payload({"data": "0x1234", "message": "0x5678"}) == b"\x124"
