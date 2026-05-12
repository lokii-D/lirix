from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from lirix.core.builder import LirixTxBuilder
from lirix.core.exceptions import LirixStateAssertionError
from lirix.shield.simulator import StateDeltaValidator

from tests.factories import build_valid_l2_payload


def test_test_v1_2_0_state_delta() -> None:
    async def _run() -> None:
        payload = build_valid_l2_payload(
            assertions=[
                {
                    "assertion_type": "return_data_int_ge",
                    "expected_value": 150,
                }
            ],
            return_data="0x96",
        )
        web3 = AsyncMock()
        validator = StateDeltaValidator(web3)
        assert await validator.validate(payload) is True

    asyncio.run(_run())


def test_test_v1_2_0_state_delta_2() -> None:
    async def _run() -> None:
        payload = build_valid_l2_payload(
            assertions=[
                {
                    "assertion_type": "return_data_int_ge",
                    "expected_value": 150,
                }
            ],
            return_data="0x64",
        )
        web3 = AsyncMock()
        validator = StateDeltaValidator(web3)
        with pytest.raises(LirixStateAssertionError) as exc_info:
            await validator.validate(payload)

        assert exc_info.value.error_code == "LRX_HONEYPOT_DETECTED"
        assert exc_info.value.to_dict() == {
            "error_code": "LRX_HONEYPOT_DETECTED",
            "canonical_error_code": "LIRIX_ERR_MALICIOUS_PAYLOAD",
            "resolution_for_agent": ("Return data 100 is less than expected 150."),
            "resolution_for_developer": "Check slippage or state override configurations.",
            "value_protected": "State Integrity",
        }

    asyncio.run(_run())


def test_test_v1_2_0_state_delta_3() -> None:
    draft = (
        LirixTxBuilder(
            "transfer(address,uint256)", ["0x000000000000000000000000000000000000dEaD", 1]
        )
        .assert_erc20_balance_increase("0x0000000000000000000000000000000000000001", 25)
        .build()
    )

    assert draft["assertions"] == [
        {
            "assertion_type": "return_data_int_ge",
            "expected_value": 25,
        }
    ]
