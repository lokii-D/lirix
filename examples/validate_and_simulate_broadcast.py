# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""``validate_and_simulate`` followed by ``Lirix.extract_broadcast_fields``.

This mirrors the signing path in the README: run the pipeline, then read
``to`` / ``data`` / ``value`` from the canonical ``result["payload"]`` subtree
via :meth:`Lirix.extract_broadcast_fields`.

Configure ``rpc_urls`` for your network before expecting a successful simulation;
without RPC the call may fail fast with a Lirix exception (still demonstrates
the two-step API surface).
"""

from __future__ import annotations

from lirix import Lirix, LirixConfig


def main() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["transfer"],
        whitelisted_addresses=["0x0000000000000000000000000000000000000001"],
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    result = client.validate_and_simulate(
        "transfer",
        {
            "to": "0x0000000000000000000000000000000000000001",
            "data": "0x",
            "value": 0,
        },
    )
    tx_payload = Lirix.extract_broadcast_fields(result)
    print("extract_broadcast_fields:", tx_payload)


if __name__ == "__main__":
    main()
