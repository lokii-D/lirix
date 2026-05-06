from __future__ import annotations

import pytest
from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.core.signatures import EXACT_INPUT_SELECTOR, MOE_SWAP_SELECTOR
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3

ROUTER = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
MC3 = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
WETH = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
USDC = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
RECIPIENT = Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")


def _cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[ROUTER, MC3],
        whitelisted_addresses=[ROUTER, MC3, WETH, USDC, RECIPIENT],
    )


def test_test_l3_defi_parser_validate_rejects_short_v3_payload_route_poison() -> None:
    parser = DeFiPayloadParser(_cfg())
    short_payload = "0x" + EXACT_INPUT_SELECTOR.hex()
    with pytest.raises(MaliciousPayloadException, match="Failed to decode V3/Router swap calldata"):
        parser.validate({"to": ROUTER, "data": short_payload})

    other = Web3.to_checksum_address("0x0000000000000000000000000000000000000123")
    with pytest.raises(MaliciousPayloadException, match="must target canonical router"):
        parser.validate({"to": other, "data": short_payload + "00" * 32})


def test_test_l3_defi_parser_validate_rejects_short_v3_payload_route_poison_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    other = Web3.to_checksum_address("0x0000000000000000000000000000000000000456")
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [1, 1, [WETH, USDC], RECIPIENT, 9999999999],
    )
    with pytest.raises(MaliciousPayloadException, match="must target canonical router"):
        parser.validate({"to": other, "data": "0x" + MOE_SWAP_SELECTOR.hex() + body.hex()})


def test_test_l3_defi_parser_validate_rejects_short_v3_payload_route_poison_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = DeFiPayloadParser(_cfg())
    collected = {MC3}
    called: list[str] = []

    def fake_decode(types: list[str], body: bytes):
        return (
            [
                (ROUTER, False, EXACT_INPUT_SELECTOR + b"\x01\x02"),
                (ROUTER, False, MOE_SWAP_SELECTOR + b"\x03\x04"),
            ],
        )

    monkeypatch.setattr("lirix.layers.l3_defi_parser.eth_abi_decode", fake_decode)
    monkeypatch.setattr(
        parser,
        "_accumulate_v3_swap",
        lambda inner_body, out, *, selector: called.append("v3"),
    )
    monkeypatch.setattr(
        parser,
        "_accumulate_moe_swap",
        lambda inner_body, out, *, selector: called.append("moe"),
    )

    parser._walk_multicall(b"ignored", collected, 0)
    assert called == ["v3", "moe"]


def test_test_l3_defi_parser_validate_rejects_short_v3_payload_route_poison_4() -> None:
    parser = DeFiPayloadParser(_cfg())

    with pytest.raises(MaliciousPayloadException, match="Failed to decode V3/Router"):
        parser._accumulate_v3_swap(b"bad", set(), selector=EXACT_INPUT_SELECTOR)
    with pytest.raises(MaliciousPayloadException, match="Failed to decode Merchant Moe"):
        parser._accumulate_moe_swap(b"bad", set(), selector=MOE_SWAP_SELECTOR)

    v3_body = abi_encode(
        ["bytes", "address", "uint256", "uint256", "uint256", "bytes"],
        [bytes.fromhex(WETH[2:] + "0001f4" + USDC[2:]), RECIPIENT, 0, 1, 9999999999, b""],
    )
    with pytest.raises(MaliciousPayloadException, match="amountIn=0"):
        parser._accumulate_v3_swap(v3_body, set(), selector=EXACT_INPUT_SELECTOR)

    moe_body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [0, 1, [WETH, USDC], RECIPIENT, 9999999999],
    )
    with pytest.raises(MaliciousPayloadException, match="amountIn=0"):
        parser._accumulate_moe_swap(moe_body, set(), selector=MOE_SWAP_SELECTOR)
