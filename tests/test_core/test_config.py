# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException
from pydantic import ValidationError
from web3 import Web3


def test_lirix_config_minimal() -> None:
    cfg = LirixConfig(chain_id=1)
    assert cfg.rpc_urls == []
    assert cfg.allowed_intents == []
    assert cfg.strict_mode is True


def test_lirix_config_allowed_function_names_none_normalized() -> None:
    cfg = LirixConfig.model_validate(
        {"chain_id": 1, "strict_mode": False, "allowed_function_names": None}
    )
    assert cfg.allowed_function_names == []


def test_lirix_config_multicall_none_normalized() -> None:
    cfg = LirixConfig.model_validate(
        {"chain_id": 1, "strict_mode": False, "multicall3_address": None}
    )
    assert cfg.multicall3_address is None


def test_lirix_config_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, not_a_field=True)  # type: ignore[call-arg]


def test_lirix_config_optional_lists_normalize_none() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=None,  # type: ignore[arg-type]
        allowed_intents=None,  # type: ignore[arg-type]
        blacklisted_addresses=None,  # type: ignore[arg-type]
        whitelisted_addresses=None,  # type: ignore[arg-type]
    )
    assert cfg.rpc_urls == []
    assert cfg.allowed_intents == []
    assert cfg.blacklisted_addresses == []
    assert cfg.whitelisted_addresses == []


def test_lirix_config_rpc_urls_stripped() -> None:
    cfg = LirixConfig(chain_id=1, strict_mode=False, rpc_urls=[" http://127.0.0.1:8545 "])
    assert cfg.rpc_urls == ["http://127.0.0.1:8545"]


def test_lirix_config_allowed_intents_stripped() -> None:
    cfg = LirixConfig(chain_id=1, strict_mode=False, allowed_intents=[" transfer "])
    assert cfg.allowed_intents == ["transfer"]


def test_lirix_config_address_lowercase_normalized_to_checksum(
    vitalik_lower: str,
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_lower],
    )
    assert cfg.blacklisted_addresses[0] == vitalik_checksum


def test_lirix_config_checksum_addresses(
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_checksum],
        whitelisted_addresses=[vitalik_checksum],
    )
    assert cfg.blacklisted_addresses[0] == vitalik_checksum


def test_lirix_config_strict_overlap_forbidden(
    vitalik_checksum: str,
    other_checksum: str,
) -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=True,
            blacklisted_addresses=[vitalik_checksum, other_checksum],
            whitelisted_addresses=[vitalik_checksum],
        )


def test_lirix_config_strict_overlap_allowed_when_disabled(
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_checksum],
        whitelisted_addresses=[vitalik_checksum],
    )
    assert cfg.strict_mode is False


def test_lirix_config_strict_mode_no_overlap_ok(
    vitalik_checksum: str,
    other_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=True,
        blacklisted_addresses=[vitalik_checksum],
        whitelisted_addresses=[other_checksum],
    )
    assert cfg.strict_mode is True


def test_lirix_config_invalid_address_type() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, rpc_urls=["123"])


def test_lirix_config_rpc_urls_not_sequence() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, rpc_urls=["x"])


def test_lirix_config_empty_rpc_entry() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, rpc_urls=["  "])


def test_lirix_config_intents_not_sequence() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, allowed_intents=["x"])


def test_lirix_config_empty_intent_entry() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, allowed_intents=["  "])


def test_lirix_config_address_list_not_sequence() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, strict_mode=False, blacklisted_addresses="x")  # type: ignore[arg-type]


def test_lirix_config_address_not_hex() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, strict_mode=False, blacklisted_addresses=["0xnotanaddress"])


def test_lirix_config_address_invalid_raises_value_error_wrapped() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=["0xdead"],
        )


def test_lirix_config_address_list_rejects_non_string_entry() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=[123],  # type: ignore[list-item]
        )


def test_lirix_config_address_list_rejects_blank_string_entry() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=["  \\n  "],
        )


def test_lirix_config_address_list_rejects_empty_string_entry() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=[""],
        )


def test_lirix_config_chain_id_validation() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=-1)


def test_lirix_config_strict_overlap_blacklist_and_allowed_to() -> None:
    a = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=True,
            blacklisted_addresses=[a],
            allowed_to_addresses=[a],
        )


def test_lirix_config_allowed_function_names_bad_container() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names="transfer",  # type: ignore[arg-type]
        )


def test_lirix_config_multicall3_invalid_address() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            multicall3_address="not-an-address",
        )


def test_lirix_config_optional_contract_blank_becomes_none() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        multicall3_address="  ",
        uniswap_v2_router="",
    )
    assert cfg.multicall3_address is None
    assert cfg.uniswap_v2_router is None


def test_lirix_config_allowed_function_names_empty_entry() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names=["swap", "  "],
        )


def test_lirix_config_allowed_function_names_bad_type() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names=123,  # type: ignore[arg-type]
        )


def test_lirix_config_optional_contract_non_string() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            multicall3_address=123,  # type: ignore[arg-type]
        )
