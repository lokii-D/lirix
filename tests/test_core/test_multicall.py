from __future__ import annotations

import lirix.core.multicall as multicall_mod
import pytest
from lirix.core.exceptions import MulticallEncodingException
from lirix.core.multicall import MulticallEncoder
from lirix.core.signatures import AGGREGATE3_SELECTOR, AGGREGATE3_VALUE_SELECTOR
from web3 import Web3


def test_encode_single_aggregate3() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    enc = MulticallEncoder(mc)
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    inner = "0x70a08231" + "0" * 24 + "d8da6bf26964af9d7eed9e03e53415dedaa90093"
    out = enc.encode_transactions([{"to": weth, "data": inner}])
    assert out["to"] == mc
    assert out["value"] == 0
    assert out["access_list"] == []
    assert bytes.fromhex(out["data"][2:10]) == AGGREGATE3_SELECTOR


def test_encode_transactions_must_be_list() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    enc = MulticallEncoder(mc)
    with pytest.raises(MulticallEncodingException, match="list"):
        enc.encode_transactions(object())  # type: ignore[arg-type]


def test_encode_element_must_be_dict() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    enc = MulticallEncoder(mc)
    with pytest.raises(MulticallEncodingException, match="dict"):
        enc.encode_transactions([object()])  # type: ignore[list-item]


def test_encode_abi_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    enc = MulticallEncoder(mc)

    def boom(*args: object, **kwargs: object) -> bytes:
        raise TypeError("encode")

    monkeypatch.setattr(multicall_mod, "eth_abi_encode", boom)
    with pytest.raises(MulticallEncodingException, match="aggregate3"):
        enc.encode_transactions([{"to": weth, "data": "0x"}])
    with pytest.raises(MulticallEncodingException, match="aggregate3Value"):
        enc.encode_transactions([{"to": weth, "data": "0x", "value": 1}])


def test_encode_outer_value_wei_matches_sum_ok() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    enc = MulticallEncoder(mc)
    out = enc.encode_transactions(
        [
            {"to": weth, "data": "0x", "value": 3},
            {"to": weth, "data": "0x", "value": 2},
        ],
        outer_value_wei=5,
    )
    assert out["value"] == 5


def test_encode_outer_value_wei_mismatch_fail_closed() -> None:
    """声明的 outer msg.value 与子调用 value 之和不一致时，SDK 层 fail-closed。"""
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    enc = MulticallEncoder(mc)
    wei = 10**18
    with pytest.raises(MulticallEncodingException, match="declared outer"):
        enc.encode_transactions(
            [
                {"to": weth, "data": "0x", "value": wei},
                {"to": weth, "data": "0x", "value": wei},
            ],
            outer_value_wei=wei,
        )


def test_encode_aggregate3_value_selector() -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    enc = MulticallEncoder(mc)
    weth = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    out = enc.encode_transactions(
        [
            {"to": weth, "data": "0x", "value": 1},
            {"to": weth, "data": "0x", "value": 2},
        ]
    )
    assert out["value"] == 3
    assert bytes.fromhex(out["data"][2:10]) == AGGREGATE3_VALUE_SELECTOR


@pytest.mark.parametrize(
    "transactions,msg",
    [
        ([], "non-empty"),
        ([{}], "to"),
        ([{"to": "not"}], "valid hex"),
        ([{"to": "0x" + "11" * 20, "data": "0x0"}], "even"),
        ([{"to": "0x" + "11" * 20, "data": "0xgg"}], "valid hex"),
        ([{"to": "0x" + "11" * 20, "data": 1}], "hex string."),
        ([{"to": "0x" + "11" * 20, "data": "abcd"}], "start with"),
        ([{"to": "0x" + "11" * 20, "data": "0x", "value": -1}], "non-negative"),
        ([{"to": "0x" + "11" * 20, "data": "0x", "value": "x"}], "non-negative"),
        ("bad", "non-empty"),  # type: ignore[list-item]
    ],
)
def test_encode_validation_errors(transactions: object, msg: str) -> None:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    enc = MulticallEncoder(mc)
    with pytest.raises(MulticallEncodingException, match=msg):
        enc.encode_transactions(transactions)  # type: ignore[arg-type]
