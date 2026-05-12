from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from lirix.core.exceptions import ConfigurationGuardException

ALLOWED_EVIDENCE_STATUSES = frozenset({"ok", "rejected", "degraded", "info"})


def normalize_non_empty_token(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationGuardException(
            human_readable_reason=f"Evidence {field} must be a non-empty string.",
            context={
                "reason": "evidence_semantics",
                "field": field,
                "value_type": type(value).__name__,
            },
        )
    return value.strip()


def normalize_status(value: Any) -> str:
    token = normalize_non_empty_token(value, field="status").lower()
    if token not in ALLOWED_EVIDENCE_STATUSES:
        raise ConfigurationGuardException(
            human_readable_reason="Evidence status is not in the allowed status taxonomy.",
            context={"reason": "evidence_semantics", "field": "status", "status": token},
        )
    return token


@dataclass(frozen=True)
class EvidenceLinks:
    correlation_id: str
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"correlation_id": self.correlation_id}
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        return payload


def embed_links(details: Mapping[str, Any], *, links: EvidenceLinks) -> Dict[str, Any]:
    out = dict(details)
    out.setdefault("_links", links.to_dict())
    return out
