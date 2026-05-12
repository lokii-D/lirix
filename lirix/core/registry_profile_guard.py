# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Construction-time strict-mode validation for chain_profile registry entries."""

from __future__ import annotations

from web3 import Web3

from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException


def _registry_label_checks(keys: list[str]) -> None:
    seen_lower: set[str] = set()
    for raw_k in keys:
        label = str(raw_k).strip()
        if not label:
            raise ConfigurationGuardException(
                human_readable_reason="protocol_registry label cannot be empty or whitespace-only.",
                context={"reason": "registry_label_invalid", "label": raw_k},
            )
        if any(ch.isspace() for ch in str(raw_k)):
            raise ConfigurationGuardException(
                human_readable_reason="protocol_registry label cannot contain whitespace.",
                context={"reason": "registry_label_whitespace", "label": raw_k},
            )
        lk = label.lower()
        if lk in seen_lower:
            raise ConfigurationGuardException(
                human_readable_reason="protocol_registry labels must be unique when lowercased.",
                context={"reason": "registry_label_duplicate", "label": raw_k},
            )
        seen_lower.add(lk)


def validate_lirix_strict_registry(cfg: LirixConfig) -> None:
    """Fail-closed registry hygiene when ``strict_mode`` is enabled."""
    if not cfg.strict_mode:
        return
    prof = cfg.chain_profile or {}
    proto = dict(prof.get("protocol_registry") or {})
    addr_reg = dict(prof.get("address_registry") or {})
    _registry_label_checks(list(proto.keys()) + list(addr_reg.keys()))

    allow = set(cfg.allowed_to_addresses) | set(cfg.whitelisted_addresses)

    eth_vals: list[str] = []
    for raw in list(proto.values()) + list(addr_reg.values()):
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if Web3.is_address(s):
            eth_vals.append(Web3.to_checksum_address(s))

    if eth_vals and not allow:
        raise ConfigurationGuardException(
            human_readable_reason=(
                "strict_mode requires a non-empty allowlist when chain_profile "
                "registries contain contract addresses."
            ),
            context={"reason": "registry_allowlist_required"},
        )

    for cs in eth_vals:
        if cs not in allow:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "strict_mode registry address is not covered by allowed_to_addresses "
                    "or whitelisted_addresses."
                ),
                context={
                    "reason": "registry_address_not_allowlisted",
                    "address": cs,
                },
            )
