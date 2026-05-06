# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import (
    LirixDependencyError,
    LirixStateAssertionError,
)
from lirix.shield.simulator import SimulationEngine, StateDeltaValidator


def test_test_sandbox_simulator() -> None:
    engine = SimulationEngine("http://example.invalid")
    assert (
        engine._decode_revert(None, lambda *_: ["x"])
        == "Simulation reverted without machine-readable revert data."
    )
    assert (
        engine._decode_revert("0x1234", lambda *_: ["x"])
        == "Simulation reverted without machine-readable revert data."
    )


@pytest.mark.asyncio
async def test_async_run_simulation_raises_dependency_error_when_optional_packages_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = SimulationEngine("http://example.invalid")

    monkeypatch.setattr(
        engine,
        "_load_web3",
        lambda: (_ for _ in ()).throw(ImportError("missing")),
    )
    with pytest.raises(LirixDependencyError, match="LRX_DEP_SIMULATION_MISSING"):
        await engine.async_run_simulation("0x0000000000000000000000000000000000000001", "0x")


@pytest.mark.asyncio
async def test_state_delta_validator_covers_invalid_and_exact_mismatch() -> None:
    validator = StateDeltaValidator(web3=None)
    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_int_ge", "expected_value": "bad"}]},
            {"return_data": "0x1"},
        )
    with pytest.raises(LirixStateAssertionError, match="LRX_STATE_MISMATCH"):
        await validator.validate(
            {"assertions": [{"assertion_type": "return_data_exact", "expected_value": 2}]},
            {"return_data": "0x1"},
        )
