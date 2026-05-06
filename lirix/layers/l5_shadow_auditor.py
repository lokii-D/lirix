# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator
from web3 import Web3

from lirix.core.exceptions import LirixPolicyViolationException


class ShadowPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_slippage_bps: Optional[int] = Field(default=None, ge=0, le=10_000)
    allowed_target_contracts: Union[List[str], str] = Field(default="ANY")
    forbidden_methods: List[str] = Field(default_factory=list)

    @field_validator("allowed_target_contracts", mode="before")
    @classmethod
    def _normalize_allowed_targets(cls, value: Any) -> Union[List[str], str]:
        if value is None or value == "ANY":
            return "ANY"
        if isinstance(value, str):
            raise ValueError("allowed_target_contracts must be 'ANY' or a list of addresses.")
        if not isinstance(value, Sequence):
            raise ValueError("allowed_target_contracts must be 'ANY' or a list of addresses.")
        normalized: List[str] = []
        for raw in value:
            if not isinstance(raw, str) or not Web3.is_address(raw):
                raise ValueError("allowed_target_contracts contains an invalid address.")
            normalized.append(Web3.to_checksum_address(raw))
        return normalized

    @field_validator("forbidden_methods", mode="before")
    @classmethod
    def _normalize_forbidden_methods(cls, value: Any) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ValueError(
                "forbidden_methods must be a list of 4-byte hex selectors or method names."
            )
        normalized: List[str] = []
        for raw in value:
            if not isinstance(raw, str):
                raise ValueError("forbidden_methods entries must be strings.")
            method = raw.strip()
            if not method:
                raise ValueError("forbidden_methods entries must be non-empty strings.")
            lowered = method.lower()
            if lowered.startswith("0x"):
                if len(lowered) != 10:
                    raise ValueError(
                        "forbidden_methods selector entries must be 4-byte hex selectors."
                    )
                int(lowered[2:], 16)
                normalized.append(lowered)
                continue
            normalized.append(method)
        return normalized


class ShadowAuditor:
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
        policy = self._resolve_policy(security_policy)
        self._enforce_target_contract(payload, policy)
        self._enforce_forbidden_method(payload, policy)
        self._enforce_slippage(simulation_result, policy)
        return True

    @classmethod
    def _resolve_policy(
        cls,
        security_policy: Optional[Union[ShadowPolicySchema, Mapping[str, Any]]],
    ) -> ShadowPolicySchema:
        if security_policy is None:
            return cls._DEFAULT_POLICY
        if isinstance(security_policy, ShadowPolicySchema):
            return security_policy
        merged = cls._DEFAULT_POLICY.model_dump()
        merged.update(dict(security_policy))
        return ShadowPolicySchema.model_validate(merged)

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
