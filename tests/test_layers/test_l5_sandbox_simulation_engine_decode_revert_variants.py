# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_l5_sandbox_simulation_engine_decode_revert_variants() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._decode_revert("0x08c379a0", lambda *_: ["bad"]) == "Execution reverted: bad"
    assert (
        engine._decode_revert("0x4e487b71", lambda *_: [1])
        == "Execution reverted with Solidity panic 0x1."
    )
    assert (
        engine._decode_revert("0x12345678", lambda *_: ["x"])
        == "Execution reverted with custom error 0x12345678."
    )


def test_test_l5_sandbox_simulation_engine_decode_revert_variants_2() -> None:
    engine = SimulationEngine("http://example.invalid")
    raw = engine._normalize_payload({"message": "0x1234"})
    assert raw == bytes.fromhex("1234")
