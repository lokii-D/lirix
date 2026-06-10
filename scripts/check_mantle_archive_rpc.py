#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from urllib import request


def call(rpc: str, method: str, params: list[object]) -> dict:
    req = request.Request(
        rpc,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(2)
    rpc = sys.argv[1]
    latest = int(call(rpc, "eth_blockNumber", []).get("result", "0x0"), 16)
    probe = max(latest - 50000, 0)
    if call(rpc, "eth_getBlockByNumber", [hex(probe), False]).get("result") is None:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
