# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_normalize_payload_variants_custom_error_fallback() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._normalize_payload({"data": "execution reverted: 0x1234"}) == b"\x124"
    assert engine._normalize_payload({"data": "0xdeadbeef"}) == b"\xde\xad\xbe\xef"
    assert engine._decode_revert({"data": "0x12345678"}, lambda *_: ["x"]).startswith(
        "Execution reverted with custom error"
    )
