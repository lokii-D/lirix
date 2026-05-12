from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import pytest
from lirix.core.config_governance import validate_governance_modes
from lirix.core.exceptions import ConfigurationGuardException


@dataclass(frozen=True)
class _Cfg:
    strict_mode: bool
    blacklisted_addresses: list[str]
    whitelisted_addresses: list[str]
    allowed_to_addresses: list[str]
    rpc_evidence_mode: Any
    policy_lifecycle_mode: Any
    decoder_plugins: list[Any]
    chain_profile: Optional[Mapping[str, Any]]
    hook_contract_mode: Any
    runtime_patch_allowlist: list[str]
    l4_min_success_count: Optional[int]
    l4_min_success_ratio: Optional[float]


def test_strict_mode_forbids_blacklist_whitelist_overlap() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=["0xabc", "0xdef"],
        whitelisted_addresses=["0xdef"],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile=None,
        hook_contract_mode="legacy",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as ei:
        validate_governance_modes(cfg)
    assert ei.value.context.get("reason") == "overlap_blacklist_whitelist"


def test_strict_mode_forbids_blacklist_allowed_to_overlap() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=["0xaaa"],
        whitelisted_addresses=[],
        allowed_to_addresses=["0xaaa", "0xbbb"],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile=None,
        hook_contract_mode="legacy",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as ei:
        validate_governance_modes(cfg)
    assert ei.value.context.get("reason") == "overlap_blacklist_allowed_to"


def test_non_strict_mode_allows_overlap_for_backwards_compatibility() -> None:
    cfg = _Cfg(
        strict_mode=False,
        blacklisted_addresses=["0xabc"],
        whitelisted_addresses=["0xabc"],
        allowed_to_addresses=["0xabc"],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile=None,
        hook_contract_mode="legacy",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    validate_governance_modes(cfg)


def test_strict_mode_rejects_non_digest_policy_lifecycle() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=[],
        whitelisted_addresses=[],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="legacy",
        decoder_plugins=[],
        chain_profile={},
        hook_contract_mode="shadow",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        validate_governance_modes(cfg)
    assert exc_info.value.context.get("reason") == "policy_lifecycle_single_stack_required"


def test_strict_mode_allows_v2_only_with_digest_verified_policy_lifecycle() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=[],
        whitelisted_addresses=[],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile={},
        hook_contract_mode="shadow",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    validate_governance_modes(cfg)


def test_hook_enforce_requires_v2_only_rpc_evidence_mode() -> None:
    cfg = _Cfg(
        strict_mode=False,
        blacklisted_addresses=[],
        whitelisted_addresses=[],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_dual",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile=None,
        hook_contract_mode="enforce",
        runtime_patch_allowlist=[],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        validate_governance_modes(cfg)
    assert exc_info.value.context.get("reason") == "hook_enforce_rpc_evidence"


def test_strict_mode_forbids_protected_runtime_patch_allowlist_fields() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=[],
        whitelisted_addresses=[],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile={},
        hook_contract_mode="shadow",
        runtime_patch_allowlist=["rpc_evidence_mode"],
        l4_min_success_count=None,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        validate_governance_modes(cfg)
    assert exc_info.value.context.get("reason") == "runtime_patch_allowlist_protected_overlap"


def test_strict_mode_forbids_l4_tolerance_overrides() -> None:
    cfg = _Cfg(
        strict_mode=True,
        blacklisted_addresses=[],
        whitelisted_addresses=[],
        allowed_to_addresses=[],
        rpc_evidence_mode="v2_only",
        policy_lifecycle_mode="digest_verified",
        decoder_plugins=[],
        chain_profile={},
        hook_contract_mode="shadow",
        runtime_patch_allowlist=[],
        l4_min_success_count=1,
        l4_min_success_ratio=None,
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        validate_governance_modes(cfg)
    assert exc_info.value.context.get("reason") == "strict_l4_tolerance_forbidden"
