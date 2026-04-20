from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import SchemaValidationException
from lirix.core.signatures import MAX_L2_CALLDATA_HEX_CHARS
from lirix.layers.l2_schema_validator import SchemaValidator
from web3 import Web3

_ROUTER = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")


def _valid_base() -> dict[str, Any]:
    return {
        "to": _ROUTER,
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }


def test_l2_validate_mapping_alias() -> None:
    assert SchemaValidator().validate_mapping(_valid_base()) is True


def test_l2_happy_path() -> None:
    assert SchemaValidator().validate(_valid_base()) is True


def test_l2_accepts_exact_uint256_max_value() -> None:
    base = _valid_base()
    base["value"] = 2**256 - 1
    assert SchemaValidator().validate(base) is True


def test_l2_accepts_calldata_at_max_length_boundary() -> None:
    base = _valid_base()
    body_pairs = (MAX_L2_CALLDATA_HEX_CHARS - 2) // 2
    base["data"] = "0x" + "aa" * body_pairs
    assert len(base["data"]) == MAX_L2_CALLDATA_HEX_CHARS
    assert SchemaValidator().validate(base) is True


@pytest.mark.parametrize(
    "patch",
    [
        {"to": _ROUTER.lower()},
        {"to": "0x000000000000000000000000000000000000000g"},
        {"value": -1},
        {"value": 2**256},
        {
            "data": "0x" + "00" * ((MAX_L2_CALLDATA_HEX_CHARS - 2) // 2 + 1),
        },
        {"data": "0x0"},
        {"data": "0xgg"},
        {"data": "deadbeef"},
        {"extra_field": 1},
        {"to": _ROUTER, "function_name": ""},
    ],
    ids=[
        "non_checksum_to",
        "hallucinated_charset_address",
        "negative_value",
        "uint256_overflow_one_past_max",
        "calldata_hex_exceeds_max_length",
        "odd_length_hex_data",
        "invalid_hex_data",
        "missing_0x_prefix",
        "prompt_injection_extra_keys",
        "empty_function_name",
    ],
)
def test_l2_malicious_schema_payloads(patch: dict[str, Any]) -> None:
    base = _valid_base()
    base.update(patch)
    with pytest.raises(SchemaValidationException):
        SchemaValidator().validate(base)


def test_lirix_chain_validate_stops_at_l2() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[_ROUTER],
    )
    client = Lirix(cfg)
    bad = {
        "to": _ROUTER.lower(),
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }
    with pytest.raises(SchemaValidationException):
        client.chain_validate("swap", bad)
