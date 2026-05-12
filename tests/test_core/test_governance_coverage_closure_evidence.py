"""Evidence-focused closure coverage for governance entrypoints."""

from __future__ import annotations

import pytest
from lirix.core.evidence import ExecutionEvidence, SecurityTrace
from lirix.core.evidence_semantics import (
    EvidenceLinks,
    embed_links,
    normalize_non_empty_token,
    normalize_status,
)
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.trace_recorder import TraceRecorder


def test_evidence_semantics_and_trace_recorder_branches() -> None:
    with pytest.raises(ConfigurationGuardException):
        normalize_non_empty_token(42, field="layer")
    with pytest.raises(ConfigurationGuardException):
        normalize_status("not-a-status")
    assert EvidenceLinks(correlation_id="c").to_dict() == {"correlation_id": "c"}
    links = EvidenceLinks(correlation_id="c", session_id="s")
    assert links.to_dict()["session_id"] == "s"
    preserved = embed_links(
        {"x": 1, "_links": {"correlation_id": "prior"}},
        links=EvidenceLinks(correlation_id="ignored"),
    )
    assert preserved["_links"]["correlation_id"] == "prior"

    trace = SecurityTrace(
        correlation_id="c",
        intent="t",
        input_summary={},
        payload_summary={},
        session_id="s",
    )
    rec = TraceRecorder(trace=trace)
    assert rec.trace is trace
    step = ExecutionEvidence(
        layer="L1",
        stage="t",
        status="ok",
        details={"k": "v"},
    )
    rec.record_step(step, force_links=False)
    assert "_links" not in trace.steps[0].details
