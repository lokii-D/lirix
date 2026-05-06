# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_decode_value_error_no_args_string_passthrough() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_value_error(ValueError(), lambda *_: ["x"])
        == "Simulation reverted without a reason."
    )
    assert engine._decode_value_error(ValueError("0x12345678"), lambda *_: ["x"]).startswith(
        "Execution reverted"
    )
