from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from lirix.core.builder import LirixTxBuilder
from lirix.core.exceptions import LirixStateAssertionError
from lirix.shield.simulator import StateDeltaValidator

from tests.factories import build_valid_l2_payload


def test_state_assertion_passes() -> None:
    async def _run() -> None:
        payload = build_valid_l2_payload(
            assertions=[
                {
                    "type": "balance_change",
                    "token": "0x0000000000000000000000000000000000000001",
                    "min_delta": 0,
                }
            ]
        )
        web3 = AsyncMock()
        validator = StateDeltaValidator(web3)
        with patch.object(validator, "get_balance", AsyncMock(side_effect=[100, 150])):
            assert await validator.validate(payload) is True

    asyncio.run(_run())


def test_honeypot_detected_reverts() -> None:
    async def _run() -> None:
        payload = build_valid_l2_payload(
            assertions=[
                {
                    "type": "balance_change",
                    "token": "0x0000000000000000000000000000000000000001",
                    "min_delta": 0,
                }
            ]
        )
        web3 = AsyncMock()
        validator = StateDeltaValidator(web3)
        with (
            patch.object(validator, "get_balance", AsyncMock(side_effect=[100, 50])),
            pytest.raises(LirixStateAssertionError) as exc_info,
        ):
            await validator.validate(payload)

        assert exc_info.value.error_code == "LRX_HONEYPOT_DETECTED"
        assert exc_info.value.to_dict() == {
            "error_code": "LRX_HONEYPOT_DETECTED",
            "resolution_for_agent": (
                "Asset delta assertion failed. Potential honeypot or massive slippage."
            ),
            "resolution_for_developer": "Check min_delta configurations and contract logic.",
            "value_protected": "Token Balance",
        }

    asyncio.run(_run())


def test_fluent_builder_populates_assertions() -> None:
    draft = (
        LirixTxBuilder(
            "transfer(address,uint256)", ["0x000000000000000000000000000000000000dEaD", 1]
        )
        .assert_erc20_balance_increase("0x0000000000000000000000000000000000000001", 25)
        .build()
    )

    assert draft["assertions"] == [
        {
            "type": "balance_change",
            "token": "0x0000000000000000000000000000000000000001",
            "min_delta": 25,
        }
    ]
