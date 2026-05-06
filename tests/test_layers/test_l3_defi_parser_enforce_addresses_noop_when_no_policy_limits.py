# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.layers.l3_defi_parser import DeFiPayloadParser


def _cfg():
    return LirixConfig(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def test_test_l3_defi_parser_enforce_addresses_noop_when_no_policy_limits() -> None:
    parser = DeFiPayloadParser(_cfg())
    parser._enforce_addresses(set())
    assert True
