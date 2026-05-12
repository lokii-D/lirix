# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException
from pydantic import ValidationError
from web3 import Web3


def test_defaults_are_initialized_when_only_chain_id_provided() -> None:
    cfg = LirixConfig(chain_id=1)
    assert cfg.rpc_urls == []
    assert cfg.allowed_intents == []
    assert cfg.strict_mode is True


def test_governance_defaults_return_shadow_single_stack_profile() -> None:
    defaults = LirixConfig.governance_defaults()
    assert defaults == {
        "hook_contract_mode": "shadow",
        "policy_lifecycle_mode": "digest_verified",
        "rpc_evidence_mode": "v2_only",
    }


def test_model_validate_none_allowed_function_names_coerces_to_empty_list() -> None:
    cfg = LirixConfig.model_validate(
        {"chain_id": 1, "strict_mode": False, "allowed_function_names": None}
    )
    assert cfg.allowed_function_names == []


def test_model_validate_none_multicall_address_is_preserved_as_none() -> None:
    cfg = LirixConfig.model_validate(
        {"chain_id": 1, "strict_mode": False, "multicall3_address": None}
    )
    assert cfg.multicall3_address is None


def test_unknown_fields_are_rejected_by_pydantic_model() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, not_a_field=True)  # type: ignore[call-arg]


def test_nullable_list_fields_are_normalized_to_empty_lists() -> None:
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


def test_rpc_urls_are_trimmed_when_provided_with_whitespace() -> None:
    cfg = LirixConfig(chain_id=1, strict_mode=False, rpc_urls=[" http://127.0.0.1:8545 "])
    assert cfg.rpc_urls == ["http://127.0.0.1:8545"]


def test_allowed_intents_are_trimmed_when_provided_with_whitespace() -> None:
    cfg = LirixConfig(chain_id=1, strict_mode=False, allowed_intents=[" transfer "])
    assert cfg.allowed_intents == ["transfer"]


def test_blacklisted_addresses_are_normalized_to_checksum_format(
    vitalik_lower: str,
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_lower],
    )
    assert cfg.blacklisted_addresses[0] == vitalik_checksum


def test_shared_address_between_lists_allowed_when_not_strict(
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_checksum],
        whitelisted_addresses=[vitalik_checksum],
    )
    assert cfg.blacklisted_addresses[0] == vitalik_checksum


def test_strict_mode_rejects_overlap_when_blacklist_has_extra_entries(
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


def test_non_strict_mode_allows_overlap_between_blacklist_and_whitelist(
    vitalik_checksum: str,
) -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        blacklisted_addresses=[vitalik_checksum],
        whitelisted_addresses=[vitalik_checksum],
    )
    assert cfg.strict_mode is False


def test_strict_mode_allows_disjoint_blacklist_and_whitelist(
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


def test_multicall_address_must_be_string_or_none() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, multicall3_address=123)  # type: ignore[arg-type]


def test_rpc_urls_must_be_a_list_not_string() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, rpc_urls="x")  # type: ignore[arg-type]


def test_rpc_urls_reject_blank_entries() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, rpc_urls=["  "])


def test_allowed_intents_must_be_a_list_not_string() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, allowed_intents="x")  # type: ignore[arg-type]


def test_allowed_intents_reject_blank_entries() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(chain_id=1, strict_mode=False, allowed_intents=["  "])


def test_blacklisted_addresses_must_be_list_type() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, strict_mode=False, blacklisted_addresses="x")  # type: ignore[arg-type]


def test_blacklisted_addresses_reject_non_address_strings() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=1, strict_mode=False, blacklisted_addresses=["0xnotanaddress"])


def test_blacklisted_addresses_reject_short_hex_values() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=["0xdead"],
        )


def test_blacklisted_addresses_reject_non_string_items() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=[123],  # type: ignore[list-item]
        )


def test_blacklisted_addresses_reject_whitespace_only_values() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=["  \\n  "],
        )


def test_blacklisted_addresses_reject_empty_string_values() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            blacklisted_addresses=[""],
        )


def test_chain_id_must_be_positive_integer() -> None:
    with pytest.raises(ValidationError):
        LirixConfig(chain_id=-1)


def test_strict_mode_rejects_address_in_blacklist_and_allowed_to_lists() -> None:
    a = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=True,
            blacklisted_addresses=[a],
            allowed_to_addresses=[a],
        )


def test_allowed_function_names_must_be_list_type() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names="transfer",  # type: ignore[arg-type]
        )


def test_multicall_address_rejects_invalid_address_string() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            multicall3_address="not-an-address",
        )


def test_blank_optional_router_and_multicall_addresses_normalize_to_none() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        multicall3_address="  ",
        uniswap_v2_router="",
    )
    assert cfg.multicall3_address is None
    assert cfg.uniswap_v2_router is None


def test_allowed_function_names_reject_blank_entries() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names=["swap", "  "],
        )


def test_allowed_function_names_reject_non_list_values() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            allowed_function_names=123,  # type: ignore[arg-type]
        )


def test_multicall_address_rejects_non_string_numeric_values() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            multicall3_address=123,  # type: ignore[arg-type]
        )


def test_for_mantle_factory_populates_chain_defaults() -> None:
    cfg = LirixConfig.for_mantle()
    assert cfg.chain_id == LirixConfig.MANTLE_CHAIN_ID
    assert cfg.rpc_urls == list(LirixConfig.MANTLE_MAINNET_RPC_URLS)
    assert cfg.multicall3_address == Web3.to_checksum_address(
        "0xcA11bde05977b3631167028862bE2a173976CA11"
    )
    assert {
        Web3.to_checksum_address(addr) for addr in LirixConfig.MANTLE_ALLOWED_TO_ADDRESSES
    }.issubset(set(cfg.allowed_to_addresses))


@pytest.mark.filterwarnings(
    "ignore:policy_lifecycle_mode=legacy is retired:DeprecationWarning",
    "ignore:rpc_evidence_mode=legacy is retired:DeprecationWarning",
)
def test_retired_governance_labels_coerce_under_non_strict_config() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://rpc.example"],
        strict_mode=False,
        policy_lifecycle_mode="legacy",
        rpc_evidence_mode="legacy",
    )
    assert cfg.policy_lifecycle_mode == "digest_verified"
    assert cfg.rpc_evidence_mode == "v2_only"


@pytest.mark.filterwarnings("ignore:rpc_evidence_mode=v2_dual is retired:DeprecationWarning")
def test_retired_rpc_evidence_v2_dual_coerces() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://rpc.example"],
        strict_mode=False,
        rpc_evidence_mode="v2_dual",
    )
    assert cfg.rpc_evidence_mode == "v2_only"
