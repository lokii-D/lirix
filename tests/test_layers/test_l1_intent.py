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


def test_l1_validate_mapping_alias() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
    }
    assert IntentValidator(cfg).validate_mapping("swap", p) is True


def test_l1_happy_path() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x",
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_l1_wrong_intent_injection() -> None:
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
def test_l1_fail_closed_policy(
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
def test_l1_injection_and_policy_payloads(payload: dict[str, Any]) -> None:
    cfg = _base_cfg()
    with pytest.raises(InvalidIntentException):
        IntentValidator(cfg).validate("swap", payload)


def test_l1_swap_intent_rejects_approve_method_id() -> None:
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


def test_l1_transfer_intent_rejects_approve_method_id() -> None:
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


def test_l1_short_calldata_skips_method_reconcile() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x1234567",
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_l1_non_string_data_skips_method_reconcile() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": 12345,
    }
    assert IntentValidator(cfg).validate("swap", p) is True


def test_l1_unknown_intent_skips_method_id_binding() -> None:
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


def test_l1_invalid_hex_in_data_fail_closed_for_reconciliation() -> None:
    cfg = _base_cfg()
    p = {
        "to": cfg.allowed_to_addresses[0],
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x" + "gg" * 8,
    }
    with pytest.raises(InvalidIntentException, match="not valid hex"):
        IntentValidator(cfg).validate("swap", p)


def test_lirix_chain_validate_l1_then_stops() -> None:
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
