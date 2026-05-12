from __future__ import annotations

from lirix.core.status_aggregation import aggregate_statuses


def test_aggregate_statuses_precedence() -> None:
    assert aggregate_statuses([]) == "info"
    assert aggregate_statuses(["info", "ok"]) == "ok"
    assert aggregate_statuses(["ok", "degraded"]) == "degraded"
    assert aggregate_statuses(["ok", "rejected", "degraded"]) == "rejected"


def test_aggregate_statuses_is_order_independent() -> None:
    a = aggregate_statuses(["ok", "degraded", "info"])
    b = aggregate_statuses(["info", "ok", "degraded"])
    assert a == b == "degraded"
