# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3

from lirix.core.constants import (
    normalize_policy_lifecycle_mode,
    policy_lifecycle_integrity_enforced,
)
from lirix.core.exceptions import ConfigurationGuardException, LirixPolicyViolationException


class ShadowPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(default="lirix-default")
    policy_version: str = Field(default="1.0.0")
    environment: str = Field(default="default")
    max_slippage_bps: Optional[int] = Field(default=None, ge=0, le=10_000)
    allowed_target_contracts: Union[List[str], str] = Field(default="ANY")
    forbidden_methods: List[str] = Field(default_factory=list)

    @field_validator("allowed_target_contracts", mode="before")
    @classmethod
    def _normalize_allowed_targets(cls, value: Any) -> Union[List[str], str]:
        if value is None or value == "ANY":
            return "ANY"
        if isinstance(value, str):
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "allowed_target_contracts must be 'ANY' or a list of addresses."
                ),
                context={"field": "allowed_target_contracts", "reason": "type_invalid"},
            )
        if not isinstance(value, Sequence):
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "allowed_target_contracts must be 'ANY' or a list of addresses."
                ),
                context={"field": "allowed_target_contracts", "reason": "type_invalid"},
            )
        normalized: List[str] = []
        for raw in value:
            if not isinstance(raw, str) or not Web3.is_address(raw):
                raise ConfigurationGuardException(
                    human_readable_reason="allowed_target_contracts contains an invalid address.",
                    context={"field": "allowed_target_contracts", "reason": "address_invalid"},
                )
            normalized.append(Web3.to_checksum_address(raw))
        return normalized

    @field_validator("forbidden_methods", mode="before")
    @classmethod
    def _normalize_forbidden_methods(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "forbidden_methods must be a list of 4-byte hex selectors or method names."
                ),
                context={"field": "forbidden_methods", "reason": "type_invalid"},
            )
        normalized: List[str] = []
        for raw in value:
            if not isinstance(raw, str):
                raise ConfigurationGuardException(
                    human_readable_reason="forbidden_methods entries must be strings.",
                    context={"field": "forbidden_methods", "reason": "entry_type_invalid"},
                )
            method = raw.strip()
            if not method:
                raise ConfigurationGuardException(
                    human_readable_reason="forbidden_methods entries must be non-empty strings.",
                    context={"field": "forbidden_methods", "reason": "entry_empty"},
                )
            lowered = method.lower()
            if lowered.startswith("0x"):
                if len(lowered) != 10:
                    raise ConfigurationGuardException(
                        human_readable_reason=(
                            "forbidden_methods selector entries must be 4-byte hex selectors."
                        ),
                        context={"field": "forbidden_methods", "reason": "selector_length_invalid"},
                    )
                try:
                    int(lowered[2:], 16)
                except ValueError as exc:
                    raise ConfigurationGuardException(
                        human_readable_reason=(
                            "forbidden_methods selector entries must be valid 4-byte hex selectors."
                        ),
                        context={
                            "field": "forbidden_methods",
                            "reason": "selector_hex_invalid",
                            "value": lowered,
                        },
                    ) from exc
                normalized.append(lowered)
                continue
            normalized.append(method)
        return normalized


class PolicyVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = Field(..., min_length=1)
    environment: str = Field(default="default")
    status: str = Field(default="active")
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    signature: Optional[str] = None
    integrity_digest: Optional[str] = None
    provenance: Optional[str] = None
    rollback_to: Optional[str] = None
    policy: ShadowPolicySchema


class PolicyConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    expected: Any
    observed: Any
    reason: str


class PolicyBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bundle_id: str = Field(default="lirix-bundle")
    active_version: Optional[str] = None
    versions: List[PolicyVersion] = Field(default_factory=list)


class ShadowAuditor:
    def __init__(self, *, lifecycle_mode: str = "digest_verified") -> None:
        self._lifecycle_mode = normalize_policy_lifecycle_mode(lifecycle_mode)

    """Hard security policy override for AI-proposed assertions."""

    _DEFAULT_POLICY = ShadowPolicySchema(
        max_slippage_bps=50,
        allowed_target_contracts="ANY",
        forbidden_methods=[
            "0xa9059cbb",
            "0x095ea7b3",
            "0x23b872dd",
            "0x38ed1739",
            "0x18cbafe5",
            "0x7ff36ab5",
        ],
    )

    def audit(
        self,
        *,
        payload: Mapping[str, Any],
        simulation_result: Mapping[str, Any],
        security_policy: Optional[Union[ShadowPolicySchema, Mapping[str, Any]]] = None,
    ) -> bool:
        policy = self._resolve_policy(
            security_policy,
            lifecycle_mode=self._effective_lifecycle_mode(),
        )
        self._enforce_target_contract(payload, policy)
        self._enforce_forbidden_method(payload, policy)
        self._enforce_slippage(simulation_result, policy)
        return True

    def decision_report(
        self,
        *,
        security_policy: Optional[Union[ShadowPolicySchema, Mapping[str, Any]]] = None,
    ) -> Mapping[str, Any]:
        effective_lifecycle_mode = self._effective_lifecycle_mode()
        policy, report = self._resolve_policy_with_report(
            security_policy,
            lifecycle_mode=effective_lifecycle_mode,
        )
        return {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "environment": policy.environment,
            "mode": "enforced",
            "bundle": report,
            "lifecycle_mode": effective_lifecycle_mode,
        }

    @staticmethod
    def import_policy_bundle(raw: Mapping[str, Any]) -> PolicyBundle:
        """Validate and import an external policy bundle payload."""
        return PolicyBundle.model_validate(dict(raw))

    @staticmethod
    def export_policy_bundle(bundle: Union[PolicyBundle, Mapping[str, Any]]) -> Dict[str, Any]:
        """Export policy bundle as a stable JSON-friendly mapping."""
        if isinstance(bundle, PolicyBundle):
            return bundle.model_dump(mode="python")
        validated = PolicyBundle.model_validate(dict(bundle))
        return validated.model_dump(mode="python")

    @classmethod
    def _resolve_policy(
        cls,
        security_policy: Optional[Union[ShadowPolicySchema, Mapping[str, Any]]],
        *,
        lifecycle_mode: str = "digest_verified",
    ) -> ShadowPolicySchema:
        policy, _ = cls._resolve_policy_with_report(
            security_policy,
            lifecycle_mode=lifecycle_mode,
        )
        return policy

    @classmethod
    def _resolve_policy_with_report(
        cls,
        security_policy: Optional[Union[ShadowPolicySchema, Mapping[str, Any]]],
        *,
        lifecycle_mode: str = "digest_verified",
    ) -> tuple[ShadowPolicySchema, Mapping[str, Any]]:
        if security_policy is None:
            return cls._DEFAULT_POLICY, {"source": "default", "conflicts": []}
        if isinstance(security_policy, ShadowPolicySchema):
            return security_policy, {"source": "direct_policy", "conflicts": []}

        policy_dict = dict(security_policy)
        bundle_raw = policy_dict.pop("policy_bundle", None)
        environment = str(policy_dict.pop("policy_environment", "default"))
        preferred_version = policy_dict.pop("policy_version", None)
        policy_dict.pop("policy_lifecycle_mode", None)
        conflicts: List[PolicyConflict] = []
        source = "mapping_override"

        base = cls._DEFAULT_POLICY.model_dump()
        rollback_applied = False
        if bundle_raw is not None:
            bundle = PolicyBundle.model_validate(bundle_raw)
            source = f"bundle:{bundle.bundle_id}"
            selected = cls._select_bundle_version(
                bundle=bundle,
                environment=environment,
                preferred_version=str(preferred_version) if preferred_version is not None else None,
            )
            if selected.status != "active" and selected.rollback_to:
                rollback = cls._find_rollback_candidate(
                    bundle=bundle,
                    environment=selected.environment,
                    rollback_to=selected.rollback_to,
                )
                if rollback is not None:
                    conflicts.append(
                        PolicyConflict(
                            key="policy_version",
                            expected=selected.version,
                            observed=rollback.version,
                            reason="rollback_applied",
                        )
                    )
                    selected = rollback
                    rollback_applied = True
            if policy_lifecycle_integrity_enforced(lifecycle_mode):
                if selected.status != "active":
                    raise cls()._policy_violation(
                        "policy_status",
                        expected="active",
                        observed=selected.status,
                    )
                if not cls._verify_policy_integrity(selected):
                    raise cls()._policy_violation(
                        "policy_integrity",
                        expected="valid_integrity_digest",
                        observed=selected.integrity_digest or selected.signature,
                    )
            base = selected.policy.model_dump()
            if selected.environment != environment:
                conflicts.append(
                    PolicyConflict(
                        key="environment",
                        expected=environment,
                        observed=selected.environment,
                        reason="requested_environment_not_found_fallback_used",
                    )
                )
        for key, value in policy_dict.items():
            if key in base and base[key] != value:
                conflicts.append(
                    PolicyConflict(
                        key=key,
                        expected=base[key],
                        observed=value,
                        reason="override_applied",
                    )
                )
            base[key] = value
        return ShadowPolicySchema.model_validate(base), {
            "source": source,
            "rollback_applied": rollback_applied,
            "conflicts": [c.model_dump() for c in conflicts],
        }

    def _effective_lifecycle_mode(self) -> str:
        return normalize_policy_lifecycle_mode(self._lifecycle_mode)

    @staticmethod
    def _select_bundle_version(
        *,
        bundle: PolicyBundle,
        environment: str,
        preferred_version: Optional[str],
    ) -> PolicyVersion:
        versions = list(bundle.versions)
        if not versions:
            return PolicyVersion(
                version="default",
                environment="default",
                policy=ShadowAuditor._DEFAULT_POLICY,
            )
        if preferred_version is not None:
            for item in versions:
                if item.version == preferred_version and item.environment == environment:
                    return item
        if bundle.active_version is not None:
            for item in versions:
                if item.version == bundle.active_version and item.environment == environment:
                    return item
        for item in versions:
            if item.environment == environment:
                return item
        return versions[0]

    @staticmethod
    def _find_rollback_candidate(
        *,
        bundle: PolicyBundle,
        environment: str,
        rollback_to: str,
    ) -> Optional[PolicyVersion]:
        for item in bundle.versions:
            if item.version == rollback_to and item.environment == environment:
                return item
        return None

    @staticmethod
    def _verify_policy_integrity(version: PolicyVersion) -> bool:
        canonical = json.dumps(
            version.policy.model_dump(mode="python"),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        declared = (version.integrity_digest or version.signature or "").strip()
        if not declared:
            return False
        return declared == digest

    def _enforce_target_contract(
        self,
        payload: Mapping[str, Any],
        policy: ShadowPolicySchema,
    ) -> None:
        allowed = policy.allowed_target_contracts
        if allowed == "ANY":
            return
        raw_target = payload.get("to")
        if not isinstance(raw_target, str) or not Web3.is_address(raw_target):
            raise self._policy_violation(
                "allowed_target_contracts",
                expected=allowed,
                observed=raw_target,
            )
        target = Web3.to_checksum_address(raw_target)
        if target not in allowed:
            raise self._policy_violation(
                "allowed_target_contracts",
                expected=allowed,
                observed=target,
            )

    def _enforce_forbidden_method(
        self,
        payload: Mapping[str, Any],
        policy: ShadowPolicySchema,
    ) -> None:
        if not policy.forbidden_methods:
            return
        data = payload.get("data", "0x")
        selector = "0x"
        if isinstance(data, str) and data.startswith("0x") and len(data) >= 10:
            selector = data[:10].lower()
        function_name = payload.get("function_name")
        normalized_function_name = function_name.strip() if isinstance(function_name, str) else None
        if selector in policy.forbidden_methods or (
            normalized_function_name is not None
            and normalized_function_name in policy.forbidden_methods
        ):
            raise self._policy_violation(
                "forbidden_methods",
                expected=policy.forbidden_methods,
                observed=normalized_function_name or selector,
            )

    def _enforce_slippage(
        self,
        simulation_result: Mapping[str, Any],
        policy: ShadowPolicySchema,
    ) -> None:
        if policy.max_slippage_bps is None:
            return
        observed = self._read_metric(simulation_result, "slippage_bps")
        if observed is None:
            return
        if not isinstance(observed, (int, float)) or int(observed) > policy.max_slippage_bps:
            raise self._policy_violation(
                "max_slippage_bps",
                expected=policy.max_slippage_bps,
                observed=observed,
            )

    def _policy_violation(
        self, key: str, *, expected: Any, observed: Any
    ) -> LirixPolicyViolationException:
        return LirixPolicyViolationException(
            error_code="LRX_SHADOW_POLICY_BLOCKED",
            resolution_agent=(
                "Simulation result violates mandatory security policy. Abort execution."
            ),
            resolution_dev=(
                "Update payload route, selector, or economic bounds so execution satisfies "
                "ShadowPolicySchema."
            ),
            value_protected="Policy Integrity",
            context={
                "layer": "L5",
                "policy_key": key,
                "reason": "policy_violation",
                "expected": expected,
                "observed": observed,
            },
        )

    @staticmethod
    def _read_metric(metrics: Mapping[str, Any], key: str) -> Optional[Any]:
        direct = metrics.get(key)
        if direct is not None:
            return direct
        nested = metrics.get("metrics")
        if isinstance(nested, Mapping):
            value = nested.get(key)
            if value is not None:
                return value
        return None
