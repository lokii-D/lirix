# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session import ValidationSession


def test_session_workflow_strict_happy_path_allows_ordered_events() -> None:
    s = ValidationSession(workflow_strict=True)
    s.record_plan(objective="ship safe tx", constraints=["fail-closed"])
    s.record_draft(label="draft-1", content={"to": "0x1", "data": "0x"})
    s.record_tool_call(
        tool_name="rpc", input_summary={"nodes": 3}, output_summary={"ok": 3}, ok=True
    )
    s.record_decision(verdict="approved", rationale="ok", details={"policy_id": "p"})
    s.finalize(outcome="ok", notes="done")
    snap = s.snapshot()
    assert snap["lifecycle"] == "finalized"


def test_session_workflow_strict_finalized_allows_only_annotation() -> None:
    s = ValidationSession(workflow_strict=True)
    s.record_plan(objective="o")
    s.record_draft(label="d", content={})
    s.record_tool_call(tool_name="t", input_summary={}, output_summary={}, ok=True)
    s.record_decision(verdict="approved", rationale="r")
    s.finalize(outcome="ok")

    # annotation allowed after finalize
    s.record_event(event_type="annotation", payload={"k": "v"})
    # mutation disallowed
    with pytest.raises(ConfigurationGuardException) as exc_info:
        s.record_decision(verdict="approved", rationale="late")
    assert exc_info.value.context.get("reason") in {
        "session_fsm_finalized",
        "session_fsm_after_finalize",
    }
