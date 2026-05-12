from __future__ import annotations

from typing import Any, Dict

from lirix.core.constants import AGENT_FEEDBACK_REASON_OK, AGENT_FEEDBACK_SCHEMA_VERSION
from lirix.core.contracts import build_agent_feedback_envelope, build_agent_feedback_success


def test_agent_feedback_schema_version_single_source_contract() -> None:
    success = build_agent_feedback_success(
        stage="L1",
        intent="swap",
        correlation_id="corr_123",
    )
    failure = build_agent_feedback_envelope(
        failure_type="timeout",
        layer="L4",
        reason_code=AGENT_FEEDBACK_REASON_OK,
        retry_allowed=True,
        remediation="retry",
        details={"intent": "swap", "correlation_id": "corr_123"},
    )
    assert _schema_version(success) == AGENT_FEEDBACK_SCHEMA_VERSION
    assert _schema_version(failure) == AGENT_FEEDBACK_SCHEMA_VERSION
    assert _schema_version(success) == _schema_version(failure)


def _schema_version(payload: Dict[str, Any]) -> str:
    v = payload.get("schema_version")
    assert isinstance(v, str)
    return v

