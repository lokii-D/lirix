# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.core.exceptions import LirixSimulationError
from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_decode_revert_error_panic_messages() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_revert({"data": "0x08c379a0"}, lambda *_: [""])
        == "Execution reverted with an empty Error(string) message."
    )
    assert (
        engine._decode_revert({"data": "0x4e487b71"}, lambda *_: [1])
        == "Execution reverted with Solidity panic 0x1."
    )


@pytest.mark.asyncio
async def test_async_run_simulation_value_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = SimulationEngine("http://example.invalid")

    class _ValueErrorEth:
        def call(self, tx: dict[str, Any]) -> None:
            raise ValueError("execution reverted: 0x08c379a0")

    class _W3:
        eth = _ValueErrorEth()

    def fake_load() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3()  # noqa: SLF001

        class _ContractLogicError(Exception):
            pass

        class _Web3Exception(Exception):
            pass

        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load)
    with pytest.raises(LirixSimulationError, match="LRX_SIM_VALUE_ERROR"):
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
