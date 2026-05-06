# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_normalize_payload_prefers_data_over_message_non_dict() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._normalize_payload({"data": "0x1234", "message": "0x5678"}) == b"\x124"
    assert engine._normalize_payload(123) is None
