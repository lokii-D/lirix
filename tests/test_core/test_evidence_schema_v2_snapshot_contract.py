from __future__ import annotations

from lirix.core.evidence import (
    EVIDENCE_SCHEMA_V2,
    build_simulate_only_evidence_v2,
    build_unified_pipeline_evidence_v2,
    build_validate_only_evidence_v2,
)


def test_validate_only_evidence_v2_snapshot_contract() -> None:
    out = build_validate_only_evidence_v2(intent="swap")
    assert out["schema_version"] == EVIDENCE_SCHEMA_V2
    assert sorted(k for k in out if k != "schema_version") == ["l1", "l2", "l3"]
    assert out["l1"]["details"]["intent"] == "swap"


def test_simulate_only_evidence_v2_snapshot_contract() -> None:
    out = build_simulate_only_evidence_v2(l4_details={"x": 1}, l5_details={"y": 2})
    assert out["schema_version"] == EVIDENCE_SCHEMA_V2
    assert sorted(k for k in out if k != "schema_version") == ["l4", "l5"]


def test_unified_pipeline_evidence_v2_snapshot_contract() -> None:
    out = build_unified_pipeline_evidence_v2(
        l4_details={"x": 1},
        l5_details={"y": 2},
        policy_details={"mode": "enforced"},
    )
    assert out["schema_version"] == EVIDENCE_SCHEMA_V2
    assert sorted(k for k in out if k != "schema_version") == ["l4", "l5", "policy"]
