# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_decode_revert_error_panic_decoding_paths() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._decode_revert({"data": "0x08c379a0"}, lambda *_: ["hello"]).startswith(
        "Execution reverted"
    )
    assert engine._decode_revert({"data": "0x4e487b71"}, lambda *_: [1]).startswith(
        "Execution reverted"
    )
