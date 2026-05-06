# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix.core.config import LirixConfig
from lirix.core.exceptions import DeFiSlippageMissingException, MaliciousPayloadException
from lirix.core.signatures import EXACT_INPUT_SELECTOR
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3

ROUTER = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
WETH = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
USDC = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
RECIPIENT = Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")


def _cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[ROUTER],
        whitelisted_addresses=[ROUTER, WETH, USDC, RECIPIENT],
    )


def _v3(selector: bytes, path: bytes, *, amount_in: int = 1, amount_out_min: int = 1) -> str:
    body = abi_encode(
        ["bytes", "address", "uint256", "uint256", "uint256", "bytes"],
        [path, RECIPIENT, amount_in, amount_out_min, 9999999999, b""],
    )
    return "0x" + selector.hex() + body.hex()


def _moe(selector: bytes, *, amount_in: int = 1, amount_out_min: int = 1) -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [amount_in, amount_out_min, [WETH, USDC], RECIPIENT, 9999999999],
    )
    return "0x" + selector.hex() + body.hex()


def test_test_l3_defi_parser_v3_swap_path_validates_hops_amounts() -> None:
    parser = DeFiPayloadParser(_cfg())
    path = bytes.fromhex(WETH[2:] + "0001f4" + USDC[2:])
    assert parser.validate({"to": ROUTER, "data": _v3(EXACT_INPUT_SELECTOR, path)}) is True


def test_test_l3_defi_parser_v3_swap_path_validates_hops_amounts_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    malformed = bytes.fromhex(WETH[2:] + "00")
    valid_path = bytes.fromhex(WETH[2:] + "0001f4" + USDC[2:])
    with pytest.raises(MaliciousPayloadException, match="V3 path encoding is malformed"):
        parser.validate({"to": ROUTER, "data": _v3(EXACT_INPUT_SELECTOR, malformed)})
    with pytest.raises(DeFiSlippageMissingException, match="amountOutMinimum=0"):
        parser.validate(
            {"to": ROUTER, "data": _v3(EXACT_INPUT_SELECTOR, valid_path, amount_out_min=0)}
        )


def test_test_l3_defi_parser_v3_swap_path_validates_hops_amounts_3() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(DeFiSlippageMissingException, match="Merchant Moe"):
        parser.validate({"to": ROUTER, "data": _moe(b"\xd0\x04\xf0\xf8", amount_out_min=0)})
    with pytest.raises(MaliciousPayloadException, match="Failed to decode Merchant Moe"):
        parser.validate({"to": ROUTER, "data": "0xd004f0f8"})
