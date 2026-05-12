from __future__ import annotations

from typing import Iterable

_PRECEDENCE = {
    "rejected": 3,
    "degraded": 2,
    "ok": 1,
    "info": 0,
}


def aggregate_statuses(statuses: Iterable[str]) -> str:
    """
    Deterministically aggregate many step statuses into one.

    Precedence: rejected > degraded > ok > info.
    Unknown tokens are treated as info (lowest precedence) for compatibility.
    """
    best = "info"
    best_rank = _PRECEDENCE[best]
    for s in statuses:
        token = str(s or "").strip()
        rank = _PRECEDENCE.get(token, _PRECEDENCE["info"])
        if rank > best_rank:
            best = token if token in _PRECEDENCE else "info"
            best_rank = rank
            if best == "rejected":
                return "rejected"
    return best
