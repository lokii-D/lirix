from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol

from lirix.core.exceptions import ConfigurationGuardException


class GovernanceConfig(Protocol):
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
    l4_min_success_count: Any
    l4_min_success_ratio: Any


def validate_governance_modes(config: GovernanceConfig) -> None:
    """
    Centralized governance-mode constraints.

    This function must remain side-effect free and deterministic; it is used by
    config validation and may be referenced by replay/forensic closures.
    """
    if config.strict_mode:
        if config.l4_min_success_count is not None or config.l4_min_success_ratio is not None:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode forbids L4 tolerance overrides; keep full quorum fail-closed."
                ),
                context={"reason": "strict_l4_tolerance_forbidden"},
            )
        protected_runtime_override_fields = {
            "strict_mode",
            "hook_contract_mode",
            "policy_lifecycle_mode",
            "rpc_evidence_mode",
            "chain_profile",
            "decoder_plugins",
            "runtime_patch_allowlist",
            "allowed_to_addresses",
            "whitelisted_addresses",
            "blacklisted_addresses",
            "allowed_function_names",
            "allowed_intents",
            "multicall3_address",
            "uniswap_v2_router",
        }
        overlap_protected = set(config.runtime_patch_allowlist) & protected_runtime_override_fields
        if overlap_protected:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode forbids runtime patch allowlist entries for governance-critical "
                    "fields."
                ),
                context={
                    "reason": "runtime_patch_allowlist_protected_overlap",
                    "overlap": sorted(overlap_protected),
                },
            )
        overlap = set(config.blacklisted_addresses) & set(config.whitelisted_addresses)
        if overlap:
            raise ConfigurationGuardException(
                human_readable_reason="strict_mode forbids overlapping blacklist and whitelist.",
                context={
                    "reason": "overlap_blacklist_whitelist",
                    "overlap": sorted(overlap),
                },
            )
        bad_to = set(config.blacklisted_addresses) & set(config.allowed_to_addresses)
        if bad_to:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode forbids addresses in both blacklisted_addresses "
                    "and allowed_to_addresses."
                ),
                context={
                    "reason": "overlap_blacklist_allowed_to",
                    "overlap": sorted(bad_to),
                },
            )
        if config.rpc_evidence_mode != "v2_only":
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode requires rpc_evidence_mode=v2_only under single-stack convergence."
                ),
                context={
                    "reason": "rpc_evidence_mode_single_stack_required",
                    "rpc_evidence_mode": config.rpc_evidence_mode,
                },
            )
        if config.policy_lifecycle_mode != "digest_verified":
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode requires policy_lifecycle_mode=digest_verified under single-stack "
                    "convergence."
                ),
                context={
                    "reason": "policy_lifecycle_single_stack_required",
                    "policy_lifecycle_mode": config.policy_lifecycle_mode,
                },
            )
        if config.decoder_plugins and config.chain_profile is None:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode requires chain_profile when decoder_plugins is non-empty."
                ),
                context={"reason": "decoder_requires_chain_profile"},
            )

    if config.hook_contract_mode == "enforce" and config.rpc_evidence_mode != "v2_only":
        raise ConfigurationGuardException(
            human_readable_reason=(
                "hook_contract_mode=enforce requires rpc_evidence_mode=v2_only under "
                "single-stack convergence."
            ),
            context={
                "reason": "hook_enforce_rpc_evidence",
                "hook_contract_mode": config.hook_contract_mode,
                "rpc_evidence_mode": config.rpc_evidence_mode,
            },
        )
