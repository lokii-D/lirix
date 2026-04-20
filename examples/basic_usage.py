# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Minimal Lirix validation flow (no signing, no broadcast)."""

from __future__ import annotations

from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix import Lirix, LirixConfig
from lirix.core.signatures import SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR
from web3 import Web3


def _swap_calldata(*, path: list[str], recipient: str) -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [1, 1, [Web3.to_checksum_address(a) for a in path], recipient, 9_999_999_999],
    )
    return "0x" + SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR.hex() + body.hex()


def main() -> None:
    router = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    usdc = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
    recipient = Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")

    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[router],
        whitelisted_addresses=sorted({router, weth, usdc, recipient}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    data = _swap_calldata(path=[weth, usdc], recipient=recipient)
    ok = client.chain_validate(
        "swap",
        {
            "to": router,
            "function_name": "swapExactTokensForTokens",
            "data": data,
        },
    )
    print("chain_validate:", ok)


if __name__ == "__main__":
    main()
