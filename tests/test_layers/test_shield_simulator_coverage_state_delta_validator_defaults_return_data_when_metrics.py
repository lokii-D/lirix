# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import builtins
from typing import Any

import pytest
from lirix.core.exceptions import LirixDependencyError, LirixStateAssertionError
from lirix.shield.simulator import SimulationEngine, StateDeltaValidator


@pytest.mark.asyncio
async def test_state_delta_validator_defaults_return_data_when_metrics_not_mapping() -> None:
    validator = StateDeltaValidator(web3=None)
    assert (
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_ge", "expected_value": 0}]},
            {"metrics": [1, 2, 3]},
        )
        is True
    )


@pytest.mark.asyncio
async def test_state_delta_validator_int_le_and_exact_config_and_mismatch() -> None:
    validator = StateDeltaValidator(web3=None)

    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_le"}]},
            {"return_data": "0x1"},
        )

    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_le", "expected_value": object()}]},
            {"return_data": "0x1"},
        )

    with pytest.raises(LirixStateAssertionError, match="LRX_STATE_MISMATCH"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_le", "expected_value": 1}]},
            {"return_data": "0x2"},
        )

    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_exact"}]},
            {"return_data": "0x1"},
        )

    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_exact", "expected_value": {}}]},
            {"return_data": "0x1"},
        )


def test_test_shield_simulator_coverage_state_delta_validator_defaults_return_data_when_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if name == "eth_abi":
            raise ImportError("simulated missing eth_abi")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    engine = SimulationEngine("http://example.invalid")
    with pytest.raises(LirixDependencyError, match="LRX_DEP_SIMULATION_MISSING"):
        engine._load_web3()


def test_test_shield_simulator_coverage_state_delta_validator_defaults_return_data_when_metrics_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = SimulationEngine("http://example.invalid")
    calls: list[tuple[Any, ...]] = []

    async def fake_async_run(
        self: SimulationEngine,
        target: str,
        calldata: str,
        sender: str | None = None,
        value: int = 0,
    ) -> bool:
        calls.append((target, calldata, sender, value))
        return True

    monkeypatch.setattr(SimulationEngine, "async_run_simulation", fake_async_run)
    assert engine.run_simulation("0xaa", "0xbb", sender="0xcc", value=5) is True
    assert calls == [("0xaa", "0xbb", "0xcc", 5)]


@pytest.mark.asyncio
async def test_async_run_simulation_sets_from_when_sender_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = SimulationEngine("http://example.invalid")
    observed: dict[str, Any] = {}

    class _ContractLogicError(Exception):
        pass

    class _Web3Exception(Exception):
        pass

    class _Eth:
        def call(self, tx: dict[str, Any]) -> None:
            observed.clear()
            observed.update(tx)

    class _W3:
        eth = _Eth()

    def fake_load() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3()
        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load)
    sender = "0x00000000000000000000000000000000000000ab"
    assert await engine.async_run_simulation(
        "0x0000000000000000000000000000000000000001",
        "0x",
        sender=sender,
    )
    assert observed["from"] == sender


@pytest.mark.asyncio
async def test_async_run_simulation_awaits_async_eth_call(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = SimulationEngine("http://example.invalid")

    class _ContractLogicError(Exception):
        pass

    class _Web3Exception(Exception):
        pass

    class _AsyncEth:
        async def call(self, tx: dict[str, Any]) -> None:
            return None

    class _Eth:
        async_eth = _AsyncEth()

    class _W3:
        eth = _Eth()

    def fake_load() -> tuple[Any, Any, Any, Any]:
        engine._w3 = _W3()
        return (
            lambda *_: ["x"],
            type("W3", (), {"to_checksum_address": staticmethod(lambda v: v)}),
            _ContractLogicError,
            _Web3Exception,
        )

    monkeypatch.setattr(engine, "_load_web3", fake_load)
    assert (
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")
        is True
    )


def test_test_shield_simulator_coverage_state_delta_validator_defaults_return_data_when_metrics_3() -> (
    None
):
    engine = SimulationEngine("http://example.invalid")

    def failing_decode(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("decode failed")

    err = engine._decode_revert("0x08c379a0" + "00" * 32, failing_decode)
    assert "could not be decoded" in err

    panic = engine._decode_revert("0x4e487b71" + "00" * 32, failing_decode)
    assert "code could not be decoded" in panic


def test_test_shield_simulator_coverage_state_delta_validator_defaults_return_data_when_metrics_4() -> (
    None
):
    engine = SimulationEngine("http://example.invalid")
    decode_fn, web3_cls, _contract_logic_error, _web3_exception = engine._load_web3()
    assert callable(decode_fn)
    assert hasattr(web3_cls, "to_checksum_address")
    assert engine._w3 is not None
