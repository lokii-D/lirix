# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.core.exceptions import LirixSimulationError
from lirix.shield.simulator import SimulationEngine


def test_test_sandbox_simulator_decode_value_error_hex_to_bytes_paths() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_value_error(ValueError(), lambda *_: ["x"])
        == "Simulation reverted without a reason."
    )
    assert engine._hex_to_bytes("execution reverted: 0x1234") == b"\x124"
    assert engine._hex_to_bytes("not-hex") is None


@pytest.mark.asyncio
async def test_async_run_simulation_success_and_error_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = SimulationEngine("http://example.invalid")

    class _ContractLogicError(Exception):
        def __init__(self, data: Any) -> None:
            self.data = data

    class _Web3Exception(Exception):
        pass

    class _Eth:
        def __init__(self, mode: str) -> None:
            self.mode = mode

        def call(self, tx: dict[str, Any]) -> Any:
            if self.mode == "ok":
                return None
            if self.mode == "logic":
                raise _ContractLogicError({"data": "0x08c379a0"})
            if self.mode == "web3":
                raise _Web3Exception("rpc bad")
            raise ValueError("execution reverted: 0x08c379a0")

    class _W3:
        def __init__(self, mode: str) -> None:
            self.eth = _Eth(mode)

    def fake_load_ok() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3("ok")
        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load_ok)
    assert (
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
        is True
    )

    def fake_load_logic() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3("logic")
        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load_logic)
    with pytest.raises(LirixSimulationError, match="LRX_SIM_CONTRACT_LOGIC"):
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")

    def fake_load_web3() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3("web3")
        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load_web3)
    with pytest.raises(LirixSimulationError, match="LRX_SIM_WEB3_ERROR"):
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
