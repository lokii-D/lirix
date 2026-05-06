# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_decode_revert_handles_none_and_custom_error_payloads() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_revert(None, lambda *_: ["x"])
        == "Simulation reverted without machine-readable revert data."
    )
    assert engine._decode_revert({"data": "0x12345678"}, lambda *_: ["x"]).startswith(
        "Execution reverted with custom error"
    )
