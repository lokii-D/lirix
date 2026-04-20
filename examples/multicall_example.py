# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Encode atomic Multicall3 batch via atomic_multicall (no signing)."""

from __future__ import annotations

from typing import Any

from lirix import Lirix, LirixConfig, atomic_multicall
from web3 import Web3


def main() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")

    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mc, weth],
        whitelisted_addresses=sorted({mc, weth}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    out: dict[str, Any] = atomic_multicall(
        client,
        "swap",
        [{"to": weth, "data": "0x"}],
    )
    payload: dict[str, Any] = out["payload"]
    print("aggregate function:", payload["function_name"])


if __name__ == "__main__":
    main()
