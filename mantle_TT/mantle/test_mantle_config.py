# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from web3 import Web3


def test_for_mantle_defaults_include_safe_whitelist_and_blacklist() -> None:
    cfg = LirixConfig.for_mantle()
    assert cfg.chain_id == LirixConfig.MANTLE_CHAIN_ID
    assert cfg.rpc_urls == list(LirixConfig.MANTLE_MAINNET_RPC_URLS)
    assert cfg.multicall3_address == Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    assert cfg.uniswap_v2_router == Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a")
    assert Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a") in cfg.allowed_to_addresses
    assert Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D") in cfg.whitelisted_addresses
    assert Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11") in cfg.whitelisted_addresses
    assert Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2") in cfg.whitelisted_addresses
    assert Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48") in cfg.whitelisted_addresses
    assert Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955") in cfg.whitelisted_addresses
    assert Web3.to_checksum_address("0x000000000000000000000000000000000000bEEF") in cfg.blacklisted_addresses


def test_for_mantle_testnet_uses_testnet_chain_and_rpc() -> None:
    cfg = LirixConfig.for_mantle(testnet=True, strict_mode=False)
    assert cfg.chain_id == LirixConfig.MANTLE_TESTNET_CHAIN_ID
    assert cfg.rpc_urls == list(LirixConfig.MANTLE_TESTNET_RPC_URLS)
    assert cfg.strict_mode is False
