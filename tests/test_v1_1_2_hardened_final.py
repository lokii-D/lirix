import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import lirix.core.calldata_builder as calldata_builder_mod
import lirix.shield.simulator as shield_sim
import pytest
from lirix.core.calldata_builder import CalldataBuilder
from lirix.core.exceptions import (
    LirixHallucinationError,
    LirixSimulationError,
)
from lirix.shield.simulator import SimulationEngine

from tests.conftest import LOCAL_ANVIL_RPC_LOCALHOST_URL

pytest_plugins = ("pytest_asyncio",)


@patch.object(shield_sim, "Web3", create=True)
def test_test_v1_1_2_hardened_final_2(mock_web3: Any) -> None:
    async def boom(_: object) -> None:
        raise ValueError({"data": "0x08c379a0"})

    async def _run() -> None:
        mock_web3.return_value = SimpleNamespace(
            eth=SimpleNamespace(async_eth=SimpleNamespace(call=AsyncMock(side_effect=boom)))
        )
        engine = SimulationEngine(LOCAL_ANVIL_RPC_LOCALHOST_URL)
        engine._w3 = SimpleNamespace(
            eth=SimpleNamespace(async_eth=SimpleNamespace(call=AsyncMock(side_effect=boom)))
        )

        def _mock_load_web3() -> tuple[Any, Any, type[RuntimeError], type[RuntimeError]]:
            return (
                lambda _types, _data: ("decoded",),
                SimpleNamespace(to_checksum_address=lambda v: v),
                RuntimeError,
                RuntimeError,
            )

        cast(Any, engine)._load_web3 = _mock_load_web3
        with pytest.raises(LirixSimulationError) as excinfo:
            await engine.async_run_simulation(
                "0x000000000000000000000000000000000000dEaD", "0x1234"
            )
        assert excinfo.value.to_dict()["error_code"] == "LRX_SIM_VALUE_ERROR"

    asyncio.run(_run())


@patch.object(calldata_builder_mod, "Web3")
def test_test_v1_1_2_hardened_final_4(mock_web3: object) -> None:
    cast(Any, mock_web3).is_address.return_value = False
    builder = CalldataBuilder()
    with pytest.raises(LirixHallucinationError):
        builder.build(
            "transfer(address,uint256)", ["0x000000000000000000000000000000000000dead", 1]
        )
