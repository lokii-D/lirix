from __future__ import annotations

from typing import Any

from web3 import Web3

_DEFAULT_TO = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")


def build_valid_l2_payload(**overrides: Any) -> dict[str, Any]:
    """Build a schema-safe L2 transaction draft for tests.

    The defaults are intentionally strict so tests can mutate individual fields
    with ``**overrides`` without accidentally tripping Pydantic validation.
    """

    payload: dict[str, Any] = {
        "to": _DEFAULT_TO,
        "function_name": "transfer",
        "value": 0,
        "data": "0x",
    }
    assertions = overrides.pop("assertions", None)
    payload.update(overrides)
    if assertions is not None:
        payload["assertions"] = assertions
    return payload
