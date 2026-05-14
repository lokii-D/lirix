# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3


def _cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        blacklisted_addresses=["0x0000000000000000000000000000000000000002"],
    )


def test_l3_defi_parser_enforce_addresses_noop_when_empty_set() -> None:
    parser = DeFiPayloadParser(_cfg())
    parser._enforce_addresses(set())


def test_l3_defi_parser_enforce_addresses_rejects_blacklisted_touched_address() -> None:
    parser = DeFiPayloadParser(_cfg())
    blocked = Web3.to_checksum_address("0x0000000000000000000000000000000000000002")
    with pytest.raises(MaliciousPayloadException, match="block-listed"):
        parser._enforce_addresses({blocked})
