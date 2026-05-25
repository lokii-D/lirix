# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixSimulationError
from lirix.shield.simulator import SimulationEngine, StateDeltaValidator


def test_mantle_simulator_decodes_error_string_payload() -> None:
    engine = SimulationEngine("http://example.invalid")
    reason = engine._decode_revert(  # noqa: SLF001
        "execution reverted: 0x08c379a0",
        lambda *_: ["Mantle revert reason"],
    )
    assert reason == "Execution reverted: Mantle revert reason"


def test_mantle_simulator_decodes_panic_payload() -> None:
    engine = SimulationEngine("http://example.invalid")
    reason = engine._decode_revert(  # noqa: SLF001
        "0x4e487b71" + "00" * 31 + "11",
        lambda *_: [17],
    )
    assert reason == "Execution reverted with Solidity panic 0x11."


@pytest.mark.asyncio
async def test_mantle_state_delta_validator_reads_nested_metrics() -> None:
    validator = StateDeltaValidator(web3=None)
    payload = {
        "assertions": [
            {"assertion_type": "return_data_int_ge", "expected_value": 7},
            {"assertion_type": "return_data_int_le", "expected_value": 9},
        ]
    }
    assert await validator.validate(payload, {"metrics": {"return_data": "0x8"}}) is True


@pytest.mark.asyncio
async def test_mantle_state_delta_validator_empty_assertions_is_noop() -> None:
    validator = StateDeltaValidator(web3=None)
    assert await validator.validate({"assertions": []}, {"return_data": "0x1"}) is True


@pytest.mark.asyncio
async def test_mantle_simulation_value_error_decodes_none_args() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_value_error(ValueError(), lambda *_: ["x"]) == "Simulation reverted without a reason."
    )  # noqa: SLF001


@pytest.mark.asyncio
async def test_mantle_async_run_simulation_value_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = SimulationEngine("http://example.invalid")

    class _Eth:
        def call(self, tx: dict[str, object]) -> None:
            raise ValueError("execution reverted: 0x08c379a0")

    class _W3:
        def __init__(self) -> None:
            self.eth = _Eth()

    monkeypatch.setattr(
        engine,
        "_load_web3",
        lambda: (
            (lambda *_: ["x"]),
            type("_W3Cls", (), {"to_checksum_address": staticmethod(lambda x: x)}),
            type("_LogicError", (Exception,), {}),
            type("_Web3Exception", (Exception,), {}),
        ),
    )
    engine._w3 = _W3()  # noqa: SLF001
    with pytest.raises(LirixSimulationError, match="LRX_SIM_VALUE_ERROR"):
        await engine.async_run_simulation(
            "0x0000000000000000000000000000000000000001",
            "0x",
        )
