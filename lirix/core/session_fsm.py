from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence, Tuple

from lirix.core.exceptions import ConfigurationGuardException

Lifecycle = Literal["open", "running", "finalized"]

_WORKFLOW_PREREQS: dict[str, frozenset[str]] = {
    "draft": frozenset({"plan"}),
    "tool_call": frozenset({"draft"}),
    "decision": frozenset({"tool_call"}),
    "finalize": frozenset({"decision"}),
}

_WORKFLOW_TRACKED: frozenset[str] = frozenset(
    {"plan", "draft", "tool_call", "decision", "finalize", "annotation"}
)


def _session_workflow_events_seen(timeline: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    seen: set[str] = set()
    for item in timeline:
        if not isinstance(item, Mapping):
            continue
        if item.get("kind") != "session_event":
            continue
        et = item.get("event_type")
        if isinstance(et, str) and et in _WORKFLOW_TRACKED:
            seen.add(et)
    return frozenset(seen)


@dataclass(frozen=True)
class SessionEvent:
    kind: str
    event_type: str | None = None


def _tail_event_types(timeline: Sequence[Mapping[str, Any]], *, limit: int = 25) -> Tuple[str, ...]:
    out = []
    for item in reversed(list(timeline)[-limit:]):
        if not isinstance(item, Mapping):
            continue
        if item.get("kind") != "session_event":
            continue
        et = item.get("event_type")
        if isinstance(et, str):
            out.append(et)
    return tuple(out)


class SessionFSM:
    """
    Strict, minimal legality constraints for ValidationSession timelines.

    Intentionally small:
    - Enforces lifecycle transition safety (no mutation after finalized).
    - Enforces that finalize is at most once.
    - Ensures decision isn't recorded after finalize.
    """

    def validate_append(
        self,
        *,
        lifecycle: Lifecycle,
        timeline: Sequence[Mapping[str, Any]],
        incoming: SessionEvent,
        workflow_strict: bool = False,
    ) -> None:
        if lifecycle == "finalized" and (
            incoming.kind != "session_event" or incoming.event_type != "annotation"
        ):
            raise ConfigurationGuardException(
                human_readable_reason="ValidationSession is finalized; mutation not allowed.",
                context={"reason": "session_fsm_finalized", "incoming": incoming.__dict__},
            )

        if (
            workflow_strict
            and incoming.kind == "session_event"
            and isinstance(incoming.event_type, str)
        ):
            et = incoming.event_type
            if et in _WORKFLOW_PREREQS:
                need = _WORKFLOW_PREREQS[et]
                seen = _session_workflow_events_seen(timeline)
                if not need.issubset(seen):
                    raise ConfigurationGuardException(
                        human_readable_reason=(
                            "Strict session workflow violated: missing prerequisite events."
                        ),
                        context={
                            "reason": "session_fsm_workflow_order",
                            "event_type": et,
                            "required_prior": sorted(need),
                            "seen": sorted(seen),
                        },
                    )

        tail = _tail_event_types(timeline)
        if incoming.kind == "session_event" and incoming.event_type == "finalize":
            if "finalize" in tail:
                raise ConfigurationGuardException(
                    human_readable_reason="ValidationSession finalize may only be recorded once.",
                    context={"reason": "session_fsm_finalize_once"},
                )
            return

        if (
            incoming.kind == "session_event"
            and incoming.event_type in {"decision", "tool_call", "draft", "plan"}
            and "finalize" in tail
        ):
            raise ConfigurationGuardException(
                human_readable_reason="Session events after finalize are not allowed.",
                context={
                    "reason": "session_fsm_after_finalize",
                    "event_type": incoming.event_type,
                },
            )
