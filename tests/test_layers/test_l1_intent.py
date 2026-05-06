# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Callable

import pytest
from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import InvalidIntentException
from lirix.layers.l1_intent_validator import IntentValidator
from tests.test_layers.conftest import mainnet_router, token_usdc
from web3 import Web3


def _base_cfg() -> LirixConfig:
    r = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
    return LirixConfig(
        chain_id=1,
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[r],
    )


def test_validate_mapping_accepts_minimal_allowed_swap_payload() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
    }
    assert IntentValidator(cfg).validate_mapping("swap", p) is True


def test_validate_accepts_valid_swap_payload_with_value_and_data() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_validate_rejects_intent_not_in_allowlist() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }
    with pytest.raises(InvalidIntentException, match="Intent is not in allowed_intents"):
        IntentValidator(cfg).validate("prompt_inject_bypass", p)


@pytest.mark.parametrize(  # type: ignore[misc]
    "mutator,exc_match",
    [
        (lambda c: c.model_copy(update={"allowed_intents": []}), "allowed_intents"),
        (
            lambda c: c.model_copy(update={"allowed_function_names": []}),
            "allowed_function_names",
        ),
        (
            lambda c: c.model_copy(update={"allowed_to_addresses": []}),
            "allowed_to_addresses",
        ),
    ],
    ids=[
        "empty_allowed_intents",
        "empty_function_whitelist",
        "empty_to_whitelist",
    ],
)
def test_validate_rejects_when_required_allowlists_are_empty(
    mutator: Callable[[LirixConfig], LirixConfig],
    exc_match: str,
) -> None:
    cfg = mutator(_base_cfg())
    p = {
        "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }
    with pytest.raises(InvalidIntentException, match=exc_match):
        IntentValidator(cfg).validate("swap", p)


@pytest.mark.parametrize(  # type: ignore[misc]
    "payload",
    [
        {"function_name": "swapExactTokensForTokens"},
        {"to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")},
        {"to": "0x123", "function_name": "swapExactTokensForTokens"},
        {
            "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
            "function_name": "",
        },
        {
            "to": Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11"),
            "function_name": "swapExactTokensForTokens",
        },
    ],
    ids=[
        "missing_to",
        "missing_function_name",
        "hallucinated_short_address",
        "empty_function_name",
        "to_not_in_whitelist",
    ],
)
def test_validate_rejects_payloads_with_missing_or_invalid_fields(payload: dict[str, Any]) -> None:
    cfg = _base_cfg()
    with pytest.raises(InvalidIntentException):
        IntentValidator(cfg).validate("swap", payload)


def test_validate_rejects_erc20_approve_selector_under_swap_intent() -> None:
    cfg = _base_cfg()
    spender = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    body = abi_encode(["address", "uint256"], [spender, 10**18])
    data = "0x095ea7b3" + body.hex()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": data,
    }
    with pytest.raises(InvalidIntentException, match="Declared intent"):
        IntentValidator(cfg).validate("swap", p)


def test_validate_rejects_erc20_approve_selector_under_transfer_intent() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        allowed_intents=["transfer"],
        allowed_function_names=["transfer"],
        allowed_to_addresses=[token_usdc()],
    )
    body = abi_encode(["address", "uint256"], [mainnet_router(), 10**12])
    data = "0x095ea7b3" + body.hex()
    p = {
        "to": token_usdc(),
        "function_name": "transfer",
        "value": 0,
        "data": data,
    }
    with pytest.raises(InvalidIntentException, match="Declared intent"):
        IntentValidator(cfg).validate("transfer", p)


def test_validate_allows_odd_length_hex_data_by_fail_open_policy() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x1234567",
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_validate_allows_non_string_data_by_fail_open_policy() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": 12345,
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_validate_allows_non_risky_selector_for_non_swap_intent() -> None:
    r = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        allowed_intents=["airdrop"],
        allowed_function_names=["claim"],
        allowed_to_addresses=[r],
    )
    p = {
        "to": r,
        "function_name": "claim",
        "value": 0,
        "data": "0x095ea7b3" + "00" * 32,
    }
    assert IntentValidator(cfg).validate("airdrop", p) is True


def test_validate_rejects_non_hex_data_string() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x" + "gg" * 8,
    }
    with pytest.raises(InvalidIntentException, match="not valid hex"):
        IntentValidator(cfg).validate("swap", p)


def test_chain_validate_rejects_function_not_in_allowlist() -> None:
    cfg = _base_cfg()
    client = Lirix(cfg)
    bad = {
        "to": Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        "function_name": "evilSwap",
        "value": 0,
        "data": "0x",
    }
    with pytest.raises(InvalidIntentException):
        client.chain_validate("swap", bad)
