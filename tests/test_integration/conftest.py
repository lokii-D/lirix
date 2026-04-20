from __future__ import annotations

from pathlib import Path

import pytest
from web3 import Web3

_CANONICAL_MULTICALL3 = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")


def _local_anvil_web3() -> Web3 | None:
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545", request_kwargs={"timeout": 3}))
    try:
        if not w3.is_connected():
            return None
    except Exception:  # noqa: BLE001
        return None
    return w3


@pytest.fixture()
def deploy_multicall3_locally() -> Web3:
    """纯净 Anvil：若无 Multicall3 字节码则 ``anvil_setCode`` 注入官方 runtime。

    不依赖 fork 或外网。
    """
    w3 = _local_anvil_web3()
    if w3 is None:
        pytest.skip("Start anvil on http://127.0.0.1:8545 for integration tests.")
    if len(w3.eth.get_code(_CANONICAL_MULTICALL3)) > 2:
        return w3
    hex_path = Path(__file__).with_name("multicall3_runtime.hex")
    if not hex_path.is_file():
        pytest.skip(f"Missing bytecode file: {hex_path}")
    code = hex_path.read_text(encoding="ascii").strip()
    raw = w3.provider.make_request("anvil_setCode", [_CANONICAL_MULTICALL3, code])
    if isinstance(raw, dict) and raw.get("error"):
        pytest.skip(f"anvil_setCode unsupported or failed: {raw!r}")
    if len(w3.eth.get_code(_CANONICAL_MULTICALL3)) <= 2:
        pytest.skip("anvil_setCode did not install Multicall3 runtime.")
    return w3
