"""Session-focused closure coverage for governance entrypoints."""

from __future__ import annotations

import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.core.session import ValidationSession
from lirix.core.session_fsm import SessionEvent, SessionFSM


def test_session_fsm_tail_and_finalize_rules() -> None:
    fsm = SessionFSM()
    bad_tail = [
        "not-a-mapping",
        {"kind": "session_event", "event_type": 99},
    ]
    fsm.validate_append(
        lifecycle="running",
        timeline=bad_tail,
        incoming=SessionEvent(kind="session_event", event_type="plan"),
    )
    timeline: list = [
        {"kind": "session_event", "event_type": "finalize", "status": "ok"},
    ]
    with pytest.raises(ConfigurationGuardException):
        fsm.validate_append(
            lifecycle="running",
            timeline=timeline,
            incoming=SessionEvent(kind="session_event", event_type="finalize"),
        )
    with pytest.raises(ConfigurationGuardException):
        fsm.validate_append(
            lifecycle="running",
            timeline=timeline,
            incoming=SessionEvent(kind="session_event", event_type="decision"),
        )


def test_validation_session_forensic_bundle_branch_coverage() -> None:
    sess = ValidationSession()
    sess.timeline.extend(
        [
            {
                "kind": "session_event",
                "status": "rejected",
                "payload": {
                    "details": {
                        "context": {
                            "layer": "L2",
                            "reason": "first",
                            "hook_result": {"failure_level": "soft"},
                        }
                    }
                },
            },
            {
                "kind": "session_event",
                "status": "rejected",
                "payload": {
                    "details": {
                        "context": {
                            "hook_result": {
                                "failure_level": "fatal",
                                "hook_point": "pre_validate",
                                "error_code": "E",
                                "error_type": "t",
                            }
                        }
                    }
                },
            },
        ]
    )
    fb = sess.forensic_bundle()
    assert fb["last_rejected_step"]["layer"] == "L2"
    assert fb["fatal_hook_summary"]["failure_level"] == "fatal"


@pytest.mark.parametrize(
    ("timeline", "expected_layer", "fatal_expected"),
    [
        pytest.param(
            [
                {
                    "kind": "session_event",
                    "event_type": "decision",
                    "status": "rejected",
                    "payload": {"details": {"context": {"layer": "L9"}}},
                }
            ],
            "L9",
            False,
            id="decision-context-layer",
        ),
        pytest.param(
            [
                {
                    "kind": "session_event",
                    "status": "rejected",
                    "payload": {
                        "details": {"context": {"hook_result": {"failure_level": "fatal"}}}
                    },
                }
            ],
            None,
            True,
            id="fatal-hook-without-layer",
        ),
        pytest.param(
            [
                "noise_tail_non_mapping",
                {
                    "kind": "session_event",
                    "event_type": "decision",
                    "status": "rejected",
                    "payload": {"details": {"context": {"layer": "from_old_decision"}}},
                },
            ],
            "from_old_decision",
            False,
            id="tail-noise-keeps-valid-decision",
        ),
    ],
)
def test_validation_session_forensic_bundle_matrix(
    timeline: list[object], expected_layer: str | None, fatal_expected: bool
) -> None:
    sess = ValidationSession()
    sess.timeline.extend(timeline)
    fb = sess.forensic_bundle()
    layer = fb["last_rejected_step"]["layer"] if fb["last_rejected_step"] else None
    assert layer == expected_layer
    assert (fb["fatal_hook_summary"] is not None) is fatal_expected


def test_validation_session_finalized_fsm_rejects_non_annotation() -> None:
    sess = ValidationSession()
    sess.finalize(outcome="ok", notes="x")
    with pytest.raises(ConfigurationGuardException):
        sess.record_plan(objective="x", constraints=[])
