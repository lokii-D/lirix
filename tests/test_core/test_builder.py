# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.builder import CalldataBuilder, LirixTxBuilder
from lirix.core.exceptions import LirixHallucinationError, ValidationFailedException
from web3 import Web3


def test_calldata_builder_rejects_empty_and_malformed_signatures() -> None:
    builder = CalldataBuilder()
    with pytest.raises(ValidationFailedException, match="LRX_VALIDATION_SIGNATURE_EMPTY"):
        builder.build("", [])
    with pytest.raises(ValidationFailedException, match="LRX_VALIDATION_SIGNATURE_FORMAT"):
        builder.build("transfer", [])
    assert builder.build("ping()", [])[:10] == "0x5c36b186"


def test_calldata_builder_rejects_argument_count_address_and_numeric_mismatches() -> None:
    builder = CalldataBuilder()
    with pytest.raises(ValidationFailedException, match="LRX_VALIDATION_ARG_COUNT"):
        builder.build("transfer(address,uint256)", ["0x0000000000000000000000000000000000000001"])
    with pytest.raises(LirixHallucinationError, match="LRX_HALLUCINATION_ADDRESS"):
        builder.build("transfer(address,uint256)", ["bad", 1])
    with pytest.raises(ValidationFailedException, match="LRX_VALIDATION_NUMERIC_TYPE"):
        builder.build(
            "transfer(address,uint256)",
            [Web3.to_checksum_address("0x0000000000000000000000000000000000000001"), "1"],
        )


def test_lirix_tx_builder_adds_balance_assertion_and_bridge_metadata() -> None:
    tx = LirixTxBuilder().assert_erc20_balance_increase(
        "0x0000000000000000000000000000000000000001", 5
    )
    tx = tx.bridge("LayerZero", 1, 2, 3)
    built = tx.build()
    assert "assertions" in built
    assert built["to"] == Web3.to_checksum_address("0x1111111111111111111111111111111111111111")
    assert built["function_name"] == "send"
