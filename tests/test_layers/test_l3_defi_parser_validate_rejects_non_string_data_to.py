# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix.core.config import LirixConfig
from lirix.core.exceptions import DeFiSlippageMissingException, MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from tests.test_layers.conftest import build_swap_calldata, mainnet_router, token_weth
from web3 import Web3


def _cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def _swap(selector: str, recipient: str = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955") -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [
            1,
            1,
            [Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")],
            recipient,
            1,
        ],
    )
    return selector + body.hex()


def test_test_l3_defi_parser_validate_rejects_non_string_data_to() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(MaliciousPayloadException, match="to must be a string address"):
        parser.validate({"to": 1, "data": "0x"})
    with pytest.raises(MaliciousPayloadException, match="data must be a string"):
        parser.validate({"to": "0x0000000000000000000000000000000000000001", "data": 1})


def test_test_l3_defi_parser_validate_rejects_non_string_data_to_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    assert (
        parser.validate(
            {
                "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
                "data": "0x",
            }
        )
        is True
    )
    with pytest.raises(MaliciousPayloadException, match="data is not valid hex"):
        parser.validate(
            {
                "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
                "data": "0xzz",
            }
        )


def test_test_l3_defi_parser_validate_rejects_non_string_data_to_3() -> None:
    parser = DeFiPayloadParser(_cfg())
    router = mainnet_router()
    data = build_swap_calldata(path=[token_weth()], recipient=router, amount_out_min=0)
    with pytest.raises(DeFiSlippageMissingException, match="amountOutMin=0"):
        parser.validate({"to": router, "data": data})
