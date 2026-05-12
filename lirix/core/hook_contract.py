"""Hook contract registry: in-process timeout + structured results (not an OS sandbox).

Future backends may add stronger isolation; today hooks share the Lirix process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, FrozenSet, Mapping, MutableMapping, Optional, Tuple


@dataclass(frozen=True)
class ReadonlyHookPayload:
    data: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ReadonlyHookPayload:
        return cls(data=MappingProxyType(dict(payload)))


@dataclass(frozen=True)
class HookDecision:
    status: str
    reason: str = ""
    failure_level: str = "soft"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HookPatch:
    updates: Dict[str, Any]
    target: str = "payload"
    reason: str = ""


@dataclass(frozen=True)
class HookAnnotation:
    tag: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


HookControlledResult = Tuple[type, ...]
ALLOWED_HOOK_RESULT_TYPES: HookControlledResult = (
    type(None),
    HookDecision,
    HookPatch,
    HookAnnotation,
)


class HookContractRegistry:
    def __init__(self) -> None:
        self._required_fields: Dict[str, FrozenSet[str]] = {}

    def register(self, hook_point: str, required_fields: FrozenSet[str]) -> None:
        self._required_fields[hook_point] = required_fields

    def required_fields(self, hook_point: str) -> FrozenSet[str]:
        return self._required_fields.get(hook_point, frozenset())

    def validate_payload(self, hook_point: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
        required = self.required_fields(hook_point)
        missing = sorted(k for k in required if k not in payload)
        return {
            "required_fields": sorted(required),
            "missing_fields": missing,
            "valid": not missing,
        }

    def validate_result(self, result: Any) -> bool:
        return isinstance(result, ALLOWED_HOOK_RESULT_TYPES)


def apply_hook_patch(
    target: MutableMapping[str, Any], patch: Optional[HookPatch]
) -> MutableMapping[str, Any]:
    if patch is None:
        return target
    for key, value in patch.updates.items():
        target[key] = value
    return target
