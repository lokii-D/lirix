from __future__ import annotations

from lirix import Lirix, build_for_chain_profile, replay_session
from lirix.core import canonicalize_error_code
from lirix.core.session import ValidationSession


def test_build_for_chain_profile_constructs_lirix() -> None:
    guard = build_for_chain_profile({"chain_id": 1, "profile_name": "t"})
    assert isinstance(guard, Lirix)
    assert guard.config.chain_profile is not None


def test_replay_session_returns_payload_after_verification() -> None:
    sess = ValidationSession()
    rb = sess.replay_bundle()
    snap = replay_session(rb)
    assert snap.get("session_id") == sess.session_id


def test_top_level_resolve_failure_protocol_bridge() -> None:
    guard = Lirix(rpc_urls=["https://example.invalid"])
    out = guard.resolve_failure_protocol(
        {
            "failure_protocol": {
                "failure_layer": "L1",
                "failure_type": "timeout",
                "retryable": True,
                "repair_hint": "retry",
                "details": {"context": {"reason": "timeout"}},
            }
        }
    )
    assert out["reason_code"] == "LIRIX_REASON_TIMEOUT"


def test_core_canonicalize_error_code_maps_legacy_values() -> None:
    assert canonicalize_error_code("LRX_SHADOW_POLICY_BLOCKED") == "LIRIX_ERR_POLICY_BLOCKED"
