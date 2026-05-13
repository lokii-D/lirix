# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Async simulation path (requires reachable RPC in rpc_urls)."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix import SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR, Lirix, LirixConfig
from web3 import Web3


def _swap_calldata(*, path: list[str], recipient: str) -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [1, 1, [Web3.to_checksum_address(a) for a in path], recipient, 9_999_999_999],
    )
    return "0x" + SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR.hex() + body.hex()


async def main() -> None:
    rpc = os.environ.get("LIRIX_EXAMPLE_RPC", "https://cloudflare-eth.com").strip()
    router = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    usdc = Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
    recipient = Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")

    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[rpc],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[router],
        whitelisted_addresses=sorted({router, weth, usdc, recipient}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    data = _swap_calldata(path=[weth, usdc], recipient=recipient)
    try:
        out: dict[str, Any] = await client.async_validate_and_simulate(
            "swap",
            {
                "to": router,
                "function_name": "swapExactTokensForTokens",
                "data": data,
            },
        )
    except Exception as exc:  # noqa: BLE001 — example: network / RPC variance
        print("async_validate_and_simulate failed:", exc)
        sys.exit(1)
    print("simulation keys:", sorted(out.keys()))


if __name__ == "__main__":
    asyncio.run(main())
