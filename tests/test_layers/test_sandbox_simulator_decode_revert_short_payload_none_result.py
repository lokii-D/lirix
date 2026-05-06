# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_decode_revert_handles_short_payload_and_normalize_none() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._decode_revert({"data": "0x12"}, lambda *_: ["x"]).startswith(
        "Simulation reverted without machine-readable revert data."
    )
    assert engine._normalize_payload({"data": None, "message": None}) is None
