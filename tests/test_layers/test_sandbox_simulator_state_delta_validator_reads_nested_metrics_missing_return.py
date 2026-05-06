# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.shield.simulator import SimulationEngine, StateDeltaValidator


@pytest.mark.asyncio
async def test_state_delta_validator_reads_nested_metrics_missing_return_data() -> None:
    validator = StateDeltaValidator(web3=None)
    payload = {
        "assertions": [
            {"assertion_type": "return_data_int_ge", "expected_value": 7},
            {"assertion_type": "return_data_int_le", "expected_value": 9},
        ]
    }
    assert await validator.validate(payload, {"metrics": {"return_data": "0x8"}}) is True


@pytest.mark.asyncio
async def test_state_delta_validator_handles_invalid_hex_and_unknown_assertions() -> None:
    validator = StateDeltaValidator(web3=None)
    payload = {
        "assertions": [
            {"assertion_type": "return_data_exact", "expected_value": 0},
            {"assertion_type": "unsupported", "expected_value": 1},
        ]
    }
    assert await validator.validate(payload, {"return_data": "not-hex"}) is True


def test_test_sandbox_simulator_state_delta_validator_reads_nested_metrics_missing_return() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_revert(
            "execution reverted: 0x08c379a0" + "00" * 32,
            lambda kinds, body: ["Insufficient output amount"] if kinds == ["string"] else [0],
        )
        == "Execution reverted: Insufficient output amount"
    )
    assert (
        engine._decode_revert(
            "0x4e487b71" + "00" * 32,
            lambda kinds, body: [0x11] if kinds == ["uint256"] else ["x"],
        )
        == "Execution reverted with Solidity panic 0x11."
    )
