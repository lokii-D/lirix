from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3


def test_mantle_bundle_contains_expected_whitelist() -> None:
    cfg = LirixConfig.for_mantle()
    assert cfg.chain_id == LirixConfig.MANTLE_CHAIN_ID
    assert cfg.rpc_urls == list(LirixConfig.MANTLE_MAINNET_RPC_URLS)
    assert cfg.multicall3_address == Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    assert {Web3.to_checksum_address(addr) for addr in LirixConfig.MANTLE_ALLOWED_TO_ADDRESSES}.issubset(
        set(cfg.allowed_to_addresses)
    )


def test_mantle_parser_blocks_unknown_target_when_whitelist_enabled() -> None:
    cfg = LirixConfig.for_mantle()
    parser = DeFiPayloadParser(cfg)
    payload = {
        "to": "0x0000000000000000000000000000000000000001",
        "data": "0x12345678",
    }
    with pytest.raises(MaliciousPayloadException):
        parser.validate(payload)


def test_mantle_parser_blocks_moe_swap_slippage_zero() -> None:
    cfg = LirixConfig.for_mantle()
    parser = DeFiPayloadParser(cfg)
    payload = {
        "to": "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
        "data": "0xd004f0f8" + "00" * 32 * 5,
    }
    with pytest.raises(MaliciousPayloadException):
        parser.validate(payload)
