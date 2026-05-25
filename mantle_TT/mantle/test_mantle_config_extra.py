# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException
from web3 import Web3


@pytest.mark.parametrize(
    "factory_kwargs, expected_chain_id, expected_rpc_urls",
    [
        ({}, LirixConfig.MANTLE_CHAIN_ID, list(LirixConfig.MANTLE_MAINNET_RPC_URLS)),
        (
            {"testnet": True},
            LirixConfig.MANTLE_TESTNET_CHAIN_ID,
            list(LirixConfig.MANTLE_TESTNET_RPC_URLS),
        ),
    ],
)
def test_for_mantle_selects_expected_chain_and_rpcs(
    factory_kwargs: dict[str, object],
    expected_chain_id: int,
    expected_rpc_urls: list[str],
) -> None:
    cfg = LirixConfig.for_mantle(**factory_kwargs)
    assert cfg.chain_id == expected_chain_id
    assert cfg.rpc_urls == expected_rpc_urls


def test_for_mantle_checksum_addresses_are_normalized_and_deduplicated() -> None:
    cfg = LirixConfig.for_mantle()
    assert len(cfg.allowed_to_addresses) == len(set(cfg.allowed_to_addresses))
    assert all(Web3.is_address(addr) for addr in cfg.allowed_to_addresses)
    assert Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a") in cfg.allowed_to_addresses


def test_for_mantle_strict_mode_blocks_conflicting_manual_overrides() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=LirixConfig.MANTLE_CHAIN_ID,
            rpc_urls=list(LirixConfig.MANTLE_MAINNET_RPC_URLS),
            strict_mode=True,
            allowed_intents=["swap"],
            allowed_function_names=["swap"],
            allowed_to_addresses=["0x000000000000000000000000000000000000bEEF"],
            blacklisted_addresses=["0x000000000000000000000000000000000000bEEF"],
        )
