# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from tests.conftest import LOCAL_ANVIL_RPC_URL


def _cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=[LOCAL_ANVIL_RPC_URL],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def test_test_defi_parser_validate_rejects_non_hex_short_payload() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(MaliciousPayloadException, match="data is not valid hex"):
        parser.validate({"to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "data": "oops"})
    assert (
        parser.validate({"to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "data": "0x12"})
        is True
    )


def test_test_defi_parser_validate_rejects_non_hex_short_payload_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(MaliciousPayloadException, match="Failed to decode swap calldata"):
        parser.validate(
            {"to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "data": "0x38ed1739" + "00" * 100}
        )
