from __future__ import annotations

import asyncio

import pytest
from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import RPCManager


def test_rpc_manager_failure_context_includes_disagreement_report() -> None:
    mgr = RPCManager(LirixConfig(chain_id=1, rpc_urls=["https://a.invalid", "https://b.invalid"]))
    ctx = mgr._failure_context(  # noqa: SLF001
        reason="reconcile_failed",
        errors={
            "https://a.invalid": TimeoutError("slow"),
            "https://b.invalid": ConnectionError("down"),
        },
        error_code="LRX_RPC_QUORUM_FAILED",
    )
    report = ctx["rpc_disagreement_report"]
    assert report["reason"] == "reconcile_failed"
    assert report["schema_version"] == "2.0"
    assert "taxonomy" in report
    assert report["taxonomy"]["transport"]["severity"] == "high"
    assert report["taxonomy"]["transport"]["raw_reason_code"] == "transport_error"
    assert "retry" in report["taxonomy"]["rpc_protocol"]["remediation"].lower()
    assert "https://a.invalid" in report["timeout_nodes"]
    assert "https://b.invalid" in report["unreachable_nodes"]
    assert ctx["raw_error_code"] == "LRX_RPC_QUORUM_FAILED"
    assert ctx["canonical_error_code"].startswith("LIRIX_ERR_")


def test_rpc_manager_disagreement_report_supports_suspicious_consistency_taxonomy() -> None:
    mgr = RPCManager(LirixConfig(chain_id=1, rpc_urls=["https://a.invalid"]))
    report = mgr._build_disagreement_report(  # noqa: SLF001
        reason="reconcile_failed",
        errors={"https://a.invalid": "down"},
        classified={"suspicious_consistency": ["https://a.invalid"]},
        heights=None,
    ).to_dict()
    assert report["taxonomy"]["suspicious_consistency"]["nodes"] == ["https://a.invalid"]


def test_rpc_manager_evidence_snapshot_includes_disagreement_report() -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            rpc_urls=["https://a.invalid"],
            strict_mode=False,
            rpc_evidence_mode="v2_only",
        )
    )
    mgr._last_error = {  # noqa: SLF001
        "reason": "height_spread_exceeded",
        "heights": {"https://a.invalid": 10, "https://b.invalid": 12},
        "classified": {"timeout": [], "transport": [], "other": [], "quota_exhausted": []},
    }
    snap = mgr.evidence_snapshot()
    report = snap["rpc_evidence_v2"]["details"]["rpc_disagreement_report"]
    assert report is not None
    assert report["reason"] == "height_spread_exceeded"
    assert report["taxonomy"]["consensus"]["reason_code"] in {"inconsistent_result", "none"}
    assert report["inconsistent_nodes"]


def test_rpc_manager_disagreement_report_heights_branches_are_covered() -> None:
    mgr = RPCManager(LirixConfig(chain_id=1, rpc_urls=["https://a.invalid"]))
    # vals empty branch (non-int heights)
    report1 = mgr._build_disagreement_report(  # noqa: SLF001
        reason="x",
        errors=None,
        classified=None,
        heights={"https://a.invalid": "not-int"},
    ).to_dict()
    assert report1["reason"] == "x"

    # inconsistent_nodes branch not taken (all equal ints)
    report2 = mgr._build_disagreement_report(  # noqa: SLF001
        reason="y",
        errors=None,
        classified=None,
        heights={"https://a.invalid": 1, "https://b.invalid": 1},
    ).to_dict()
    assert report2["taxonomy"]["consensus"]["reason_code"] == "none"


def test_rpc_manager_non_strict_tolerance_allows_partial_sync_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=["https://a.invalid", "https://b.invalid"],
            l4_min_success_count=1,
            rpc_evidence_mode="v2_only",
        )
    )

    def _fake_fetch(url: str) -> tuple[str, int]:
        if url.endswith("b.invalid"):
            raise TimeoutError("simulated timeout")
        return (url, 100)

    monkeypatch.setattr(mgr, "_fetch_block_number_sync", _fake_fetch)
    bn = mgr.sync_reconcile()
    assert bn == 100
    snap = mgr.evidence_snapshot()
    last_error = snap["rpc_evidence_v2"]["details"]["last_error"]
    assert last_error["reason"] == "reconcile_tolerated_partial_success"
    assert last_error["required_successes"] == 1


@pytest.mark.parametrize(
    ("ratio", "eligible_count", "expected"),
    [
        (0.01, 3, 1),
        (1 / 3, 3, 1),
        (0.34, 3, 2),
        (2 / 3, 3, 2),
        (0.67, 3, 3),
        (1.0, 3, 3),
    ],
)
def test_rpc_manager_required_successes_ratio_ceil_boundaries(
    ratio: float, eligible_count: int, expected: int
) -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=["https://a.invalid", "https://b.invalid", "https://c.invalid"],
            l4_min_success_ratio=ratio,
        )
    )
    assert mgr._required_successes(eligible_count) == expected  # noqa: SLF001


def test_rpc_manager_non_strict_tolerance_allows_partial_async_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=["https://a.invalid", "https://b.invalid"],
            l4_min_success_count=1,
            rpc_evidence_mode="v2_only",
        )
    )

    async def _fake_fetch(url: str) -> tuple[str, int]:
        if url.endswith("b.invalid"):
            raise TimeoutError("simulated timeout")
        return (url, 101)

    monkeypatch.setattr(mgr, "_fetch_block_number_async", _fake_fetch)
    block = asyncio.run(mgr.async_reconcile())
    assert block == 101
    snap = mgr.evidence_snapshot()
    assert snap["rpc_evidence_v2"]["details"]["last_error"]["reason"] == (
        "reconcile_tolerated_partial_success"
    )
    report = snap["rpc_evidence_v2"]["details"]["rpc_disagreement_report"]
    assert report["reason"] == "reconcile_tolerated_partial_success"
    assert report["taxonomy"]["rpc_protocol"]["reason_code"] == "timeout"


def test_rpc_manager_required_successes_uses_stricter_of_count_and_ratio() -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=[
                "https://a.invalid",
                "https://b.invalid",
                "https://c.invalid",
                "https://d.invalid",
            ],
            l4_min_success_count=2,
            l4_min_success_ratio=0.75,
        )
    )
    # count=2, ratio=>ceil(0.75*4)=3, stricter result must be 3.
    assert mgr._required_successes(4) == 3  # noqa: SLF001
