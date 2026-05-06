# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3


def _cfg(**overrides):
    base = dict(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )
    base.update(overrides)
    return LirixConfig(**base)


def test_test_l3_defi_parser_multicall_nesting_limit_selector_blocks() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(
        MaliciousPayloadException, match="Failed to decode Multicall3 aggregate3 arguments"
    ):
        parser._walk_multicall(
            b"bad", {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")}, 0
        )
    with pytest.raises(
        MaliciousPayloadException, match="Non-swap calldata directed at Uniswap router"
    ):
        parser.validate(
            {
                "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
                "data": "0x12345678",
            }
        )
