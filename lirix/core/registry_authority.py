from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Mapping

from lirix.core.exceptions import ConfigurationGuardException

REGISTRY_AUTHORITY_SCHEMA_VERSION = "1.0"


def _is_supported_schema_version(version: Any) -> bool:
    text = str(version)
    return text.startswith("1.")


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def registry_authority_snapshot(
    *,
    chain_registry: Mapping[str, Any],
    decoder_registry: Mapping[str, Any],
    source: str = "chain_adapter",
) -> Dict[str, Any]:
    """
    Declare authority boundary for registry semantics.

    - chain_registry authority: chain/profile governance path
    - decoder_registry authority: decoder registry governance path
    """
    chain_keys = sorted(str(k) for k in chain_registry)
    decoder_keys = sorted(str(k) for k in decoder_registry)
    authority = {
        "schema_version": REGISTRY_AUTHORITY_SCHEMA_VERSION,
        "authority_source": source,
        "chain_registry_authority": "chain_profile_registry",
        "decoder_registry_authority": "decoder_registry",
        "chain_registry_keys": chain_keys,
        "decoder_registry_keys": decoder_keys,
    }
    authority["authority_digest"] = _sha256_payload(authority)
    return authority


def assert_registry_authority_contract(authority: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = dict(authority)
    required = {
        "schema_version",
        "authority_source",
        "chain_registry_authority",
        "decoder_registry_authority",
        "chain_registry_keys",
        "decoder_registry_keys",
        "authority_digest",
    }
    missing = sorted(k for k in required if k not in snapshot)
    if missing:
        raise ConfigurationGuardException(
            human_readable_reason="registry authority snapshot missing required fields.",
            context={"reason": "registry_authority_missing_fields", "missing_fields": missing},
        )
    observed_version = snapshot.get("schema_version")
    if not _is_supported_schema_version(observed_version):
        raise ConfigurationGuardException(
            human_readable_reason="unsupported registry authority schema version.",
            context={
                "reason": "registry_authority_schema_mismatch",
                "supported_major": "1.x",
                "current_default": REGISTRY_AUTHORITY_SCHEMA_VERSION,
                "observed": observed_version,
            },
        )
    expected_digest = _sha256_payload(
        {k: v for k, v in snapshot.items() if k != "authority_digest"}
    )
    if str(snapshot["authority_digest"]) != expected_digest:
        raise ConfigurationGuardException(
            human_readable_reason="registry authority digest mismatch.",
            context={
                "reason": "registry_authority_digest_mismatch",
                "expected_digest": expected_digest,
                "observed_digest": snapshot.get("authority_digest"),
            },
        )
    return snapshot
