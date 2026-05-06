# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3


def _cfg(**overrides):
    base = dict(
        chain_id=1,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )
    base.update(overrides)
    return LirixConfig(**base)


def test_test_l3_defi_parser_direct_validation_non_string_empty_payload() -> None:
    parser = DeFiPayloadParser(_cfg())
    with pytest.raises(MaliciousPayloadException, match="data must be a string"):
        parser.validate(
            {
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "data": b"x",
            }
        )
    with pytest.raises(MaliciousPayloadException, match="to must be a string address"):
        parser.validate({"to": 1, "data": "0x"})


def test_test_l3_defi_parser_direct_validation_non_string_empty_payload_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class _Hooks:
        def invoke_hooks_isolated(self, *args, **kwargs):
            calls.append((args, kwargs))

    parser = DeFiPayloadParser(_cfg(), hooks=_Hooks())
    assert (
        parser.validate(
            {
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "data": "0x1234",
            }
        )
        is True
    )
    assert calls
