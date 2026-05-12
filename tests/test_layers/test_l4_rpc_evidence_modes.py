from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.layers.l4_rpc_manager import RPCManager


def test_rpc_evidence_mode_v2_only_emits_v2_payload_with_details() -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            rpc_urls=["https://a.invalid"],
            strict_mode=False,
            rpc_evidence_mode="v2_only",
        )
    )
    snap = mgr.evidence_snapshot()
    assert "rpc_evidence_v2" in snap
    assert snap["rpc_evidence_v2"]["schema_version"] == "2.0"
    assert snap["layer"] == "L4"
    details = snap["rpc_evidence_v2"]["details"]
    assert "selected_rpc_url" in details
    assert "health" in details


def test_rpc_evidence_mode_v2_only_hides_legacy_shape() -> None:
    mgr = RPCManager(
        LirixConfig(
            chain_id=1,
            rpc_urls=["https://a.invalid"],
            strict_mode=False,
            rpc_evidence_mode="v2_only",
        )
    )
    snap = mgr.evidence_snapshot()
    assert set(snap.keys()) == {"layer", "rpc_evidence_v2"}
    assert snap["rpc_evidence_v2"]["schema_version"] == "2.0"
