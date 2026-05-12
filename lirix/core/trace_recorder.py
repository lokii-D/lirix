from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

from lirix.core.evidence import ExecutionEvidence, SecurityTrace
from lirix.core.evidence_semantics import (
    EvidenceLinks,
    embed_links,
    normalize_non_empty_token,
    normalize_status,
)


class TraceRecorder:
    """
    Minimal, governance-focused trace recorder.

    - Enforces basic evidence semantics (non-empty tokens + allowed status taxonomy).
    - Ensures every step is linkable to correlation/session via details._links.
    - Delegates step_id generation to SecurityTrace.add_step().
    """

    def __init__(self, *, trace: SecurityTrace) -> None:
        self._trace = trace

    @property
    def trace(self) -> SecurityTrace:
        return self._trace

    def record_step(
        self,
        evidence: ExecutionEvidence,
        *,
        correlation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        force_links: bool = True,
    ) -> str:
        layer = normalize_non_empty_token(evidence.layer, field="layer")
        stage = normalize_non_empty_token(evidence.stage, field="stage")
        status = normalize_status(evidence.status)

        details: Dict[str, Any] = dict(evidence.details)
        if force_links:
            links = EvidenceLinks(
                correlation_id=str(correlation_id or self._trace.correlation_id),
                session_id=session_id if session_id is not None else self._trace.session_id,
            )
            details = embed_links(details, links=links)

        normalized = replace(evidence, layer=layer, stage=stage, status=status, details=details)
        return self._trace.add_step(normalized)
