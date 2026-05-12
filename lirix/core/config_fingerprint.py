from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping

from lirix.core.config import LirixConfig


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_nested(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(k): _normalize_nested(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_nested(x) for x in value]
    return value


def fingerprint_lirix_config(config: LirixConfig) -> str:
    """Stable hash over governance + chain surface (replay closure)."""
    profile = config.chain_profile
    profile_norm = _normalize_nested(dict(profile)) if isinstance(profile, Mapping) else None
    core: dict[str, Any] = {
        "chain_id": config.chain_id,
        "strict_mode": config.strict_mode,
        "hook_contract_mode": config.hook_contract_mode,
        "policy_lifecycle_mode": config.policy_lifecycle_mode,
        "rpc_evidence_mode": config.rpc_evidence_mode,
        "chain_profile": profile_norm,
        "allowed_to_addresses": sorted(config.allowed_to_addresses),
        "allowed_function_names": sorted(config.allowed_function_names),
        "allowed_intents": sorted(config.allowed_intents),
        "config_source_tags": dict(
            sorted((str(k), str(v)) for k, v in config.config_source_tags.items())
        ),
    }
    core["list_hashes"] = {
        "whitelisted_addresses": _canonical_hash({"v": sorted(config.whitelisted_addresses)}),
        "blacklisted_addresses": _canonical_hash({"v": sorted(config.blacklisted_addresses)}),
        "rpc_urls": _canonical_hash({"v": list(config.rpc_urls)}),
    }
    return _canonical_hash(core)


def fingerprint_registry_closure_bundle(
    *,
    chain_registry: Mapping[str, Any],
    decoder_registry: Mapping[str, Any],
) -> str:
    """Stable digest over protocol/address registries plus decoder snapshot."""
    payload = {
        "chain_registry": _normalize_nested(dict(chain_registry)),
        "decoder_registry": _normalize_nested(dict(decoder_registry)),
    }
    return _canonical_hash(payload)
