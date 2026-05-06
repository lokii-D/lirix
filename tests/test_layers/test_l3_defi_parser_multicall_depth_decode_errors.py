# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix.core.config import LirixConfig
from lirix.core.exceptions import DeFiSlippageMissingException, MaliciousPayloadException
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


def _v3_body(amount_in: int = 1, amount_out_min: int = 1, path: bytes | None = None) -> str:
    if path is None:
        path = bytes.fromhex("11" * 20 + "000bb8" + "22" * 20)
    body = abi_encode(
        ["bytes", "address", "uint256", "uint256", "uint256", "bytes"],
        [
            path,
            Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"),
            amount_in,
            amount_out_min,
            1,
            b"",
        ],
    )
    return "0x" + b"exactinput".hex()[:8] + body.hex()


def test_test_l3_defi_parser_multicall_depth_decode_errors() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(
        MaliciousPayloadException, match="Failed to decode Multicall3 aggregate3 arguments"
    ):
        parser._walk_multicall(
            b"bad", {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")}, 0
        )
    with pytest.raises(
        MaliciousPayloadException, match="Failed to decode Multicall3 aggregate3Value arguments"
    ):
        parser._walk_multicall_value(
            b"bad", {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")}, 0
        )


def test_test_l3_defi_parser_multicall_depth_decode_errors_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(DeFiSlippageMissingException, match="amountOutMinimum=0"):
        parser._accumulate_v3_swap(
            abi_encode(
                ["bytes", "address", "uint256", "uint256", "uint256", "bytes"],
                [
                    bytes.fromhex("11" * 20 + "000bb8" + "22" * 20),
                    Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"),
                    1,
                    0,
                    1,
                    b"",
                ],
            ),
            {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")},
            selector=b"1234",
        )
    with pytest.raises(MaliciousPayloadException, match="V3 path is too short"):
        parser._collect_v3_path_addresses(
            b"\x11" * 19,
            {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")},
            selector=b"1234",
        )
    with pytest.raises(MaliciousPayloadException, match="V3 path encoding is malformed"):
        parser._collect_v3_path_addresses(
            b"\x11" * 21,
            {Web3.to_checksum_address("0x0000000000000000000000000000000000000001")},
            selector=b"1234",
        )


def test_test_l3_defi_parser_multicall_depth_decode_errors_3() -> None:
    blacklisted = Web3.to_checksum_address("0x0000000000000000000000000000000000000002")
    whitelist = Web3.to_checksum_address("0x0000000000000000000000000000000000000003")
    parser = DeFiPayloadParser(
        _cfg(blacklisted_addresses=[blacklisted], whitelisted_addresses=[whitelist])
    )
    with pytest.raises(MaliciousPayloadException, match="Touched address is block-listed"):
        parser._enforce_addresses({blacklisted})
    with pytest.raises(
        MaliciousPayloadException, match="Touched address is not in whitelisted_addresses"
    ):
        parser._enforce_addresses(
            {Web3.to_checksum_address("0x0000000000000000000000000000000000000004")}
        )
