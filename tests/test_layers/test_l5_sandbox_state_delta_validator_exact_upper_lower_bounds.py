# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import LirixStateAssertionError
from lirix.shield.simulator import StateDeltaValidator


@pytest.mark.asyncio
async def test_state_delta_validator_exact_and_upper_lower_bounds() -> None:
    validator = StateDeltaValidator(web3=None)
    payload = {
        "assertions": [
            {"assertion_type": "return_data_int_ge", "expected_value": 1},
            {"assertion_type": "return_data_int_le", "expected_value": 2},
            {"assertion_type": "return_data_exact", "expected_value": 1},
        ]
    }
    assert await validator.validate(payload, {"return_data": "0x1"}) is True


@pytest.mark.asyncio
async def test_state_delta_validator_rejects_bad_config() -> None:
    validator = StateDeltaValidator(web3=None)
    payload = {"assertions": [{"assertion_type": "return_data_int_ge"}]}
    with pytest.raises(LirixStateAssertionError, match="LRX_ASSERTION_CONFIG_INVALID"):
        await validator.validate(payload, {"return_data": "0x1"})
