# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_normalize_payload_message_dict_non_string_ignored() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._normalize_payload({"message": "execution reverted: 0x1234"}) == b"\x124"
    assert engine._normalize_payload({"message": 123}) is None
