# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.core.exceptions import LirixSimulationError
from lirix.shield.simulator import SimulationEngine, StateDeltaValidator


def test_test_sandbox_simulator_decode_revert_error_panic_paths() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._decode_revert("0x08c379a0" + "00" * 32, lambda *_: ["boom"]).startswith(
        "Execution reverted"
    )
    assert engine._decode_revert("0x4e487b71" + "00" * 32, lambda *_: [17]).startswith(
        "Execution reverted with Solidity panic"
    )


def test_test_sandbox_simulator_decode_revert_error_panic_paths_2() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert engine._normalize_payload({"data": "execution reverted: 0x12"}) == bytes.fromhex("12")
    assert engine._normalize_payload({"message": "0x12"}) == bytes.fromhex("12")
    assert engine._normalize_payload(123) is None


@pytest.mark.asyncio
async def test_state_delta_validator_accepts_and_nested_metrics() -> None:
    validator = StateDeltaValidator(web3=None)
    assert await validator.validate({"assertions": []}, {"return_data": "0x1"}) is True
    assert (
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_le", "expected_value": 2}]},
            {"metrics": {"return_data": "0x2"}},
        )
        is True
    )


@pytest.mark.asyncio
async def test_async_run_simulation_success_and_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = SimulationEngine("http://example.invalid")

    class _Eth:
        def call(self, tx: dict[str, Any]) -> str:
            return "ok"

    class _Web3:
        eth = _Eth()

    monkeypatch.setattr(
        engine,
        "_load_web3",
        lambda: (
            lambda *_: ["x"],
            type("W", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            Exception,
            Exception,
        ),
    )
    engine._w3 = _Web3()
    assert (
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
        is True
    )

    def _raise(*_a: Any, **_k: Any) -> None:
        raise ValueError("execution reverted: 0x08c379a0")

    monkeypatch.setattr(engine._w3.eth, "call", _raise)
    with pytest.raises(LirixSimulationError):
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
