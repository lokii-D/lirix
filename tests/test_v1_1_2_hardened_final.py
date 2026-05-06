import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from lirix.core.builder import CalldataBuilder
from lirix.core.exceptions import (
    LirixCircuitBreakerError,
    LirixHallucinationError,
    LirixSimulationError,
)
from lirix.core.guard import LirixGuard
from lirix.shield.simulator import SimulationEngine

from tests.factories import build_valid_l2_payload

pytest_plugins = ("pytest_asyncio",)

MOCK_PATH = "web3.eth.async_eth.AsyncEth.call"


@patch(MOCK_PATH, new_callable=AsyncMock)
def test_test_v1_1_2_hardened_final(mock_call: AsyncMock) -> None:
    async def _run() -> None:
        mock_call.side_effect = asyncio.TimeoutError()
        guard = LirixGuard(rpc_url="http://localhost:8545")
        guard._simulator = cast(
            Any,
            SimpleNamespace(async_run_simulation=AsyncMock(side_effect=asyncio.TimeoutError())),
        )
        with patch("lirix.shield.simulator.Web3", create=True) as mock_web3:
            mock_web3.return_value = SimpleNamespace(
                eth=SimpleNamespace(async_eth=SimpleNamespace(call=mock_call))
            )
            with pytest.raises(LirixCircuitBreakerError):
                await guard.async_parse(build_valid_l2_payload())

    asyncio.run(_run())
    assert True


@patch("lirix.shield.simulator.Web3", create=True)
def test_test_v1_1_2_hardened_final_2(mock_web3: Any) -> None:
    async def boom(_: object) -> None:
        raise ValueError({"data": "0x08c379a0"})

    async def _run() -> None:
        mock_web3.return_value = SimpleNamespace(
            eth=SimpleNamespace(async_eth=SimpleNamespace(call=AsyncMock(side_effect=boom)))
        )
        engine = SimulationEngine("http://localhost:8545")
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


@patch("lirix.shield.simulator.Web3", create=True)
def test_test_v1_1_2_hardened_final_3(mock_web3: Any) -> None:
    async def slow(_: object) -> None:
        raise asyncio.TimeoutError()

    async def _run() -> None:
        mock_web3.return_value = SimpleNamespace(
            eth=SimpleNamespace(async_eth=SimpleNamespace(call=AsyncMock(side_effect=slow)))
        )
        guard = LirixGuard(rpc_url="http://localhost:8545")
        guard._simulator = cast(
            Any,
            SimpleNamespace(async_run_simulation=AsyncMock(side_effect=asyncio.TimeoutError())),
        )
        with pytest.raises(LirixCircuitBreakerError) as excinfo:
            await guard.async_parse(build_valid_l2_payload())
        assert excinfo.value.to_dict()["error_code"] == "LRX_TIMEOUT_BLOCK"

    asyncio.run(_run())


@patch("lirix.core.builder.Web3", create=True)
@patch("lirix.core.builder.eth_abi_encode", create=True)
def test_test_v1_1_2_hardened_final_4(_: Any, mock_web3: object) -> None:
    cast(Any, mock_web3).is_address.return_value = False
    builder = CalldataBuilder()
    with pytest.raises(LirixHallucinationError):
        builder.build(
            "transfer(address,uint256)", ["0x000000000000000000000000000000000000dead", 1]
        )


@patch("lirix.shield.simulator.Web3", create=True)
def test_test_v1_1_2_hardened_final_5(mock_web3: Any) -> None:
    async def ok(*_args: object, **_kwargs: object) -> None:
        return None

    async def _run() -> None:
        mock_web3.return_value = SimpleNamespace(
            eth=SimpleNamespace(async_eth=SimpleNamespace(call=AsyncMock(side_effect=ok)))
        )
        guard = LirixGuard(rpc_url="http://localhost:8545")
        guard._simulator = cast(
            Any, SimpleNamespace(async_run_simulation=AsyncMock(side_effect=ok))
        )
        await guard.async_parse(build_valid_l2_payload())
        assert "http://" not in str(guard.last_trace)

    asyncio.run(_run())
