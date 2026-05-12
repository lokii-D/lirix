from __future__ import annotations

from lirix.core.evidence import SimulationOutcome


def test_simulation_outcome_includes_replay_fields_and_state_delta_digest() -> None:
    outcome = SimulationOutcome(
        simulation_ok=True,
        layer="L5",
        details={"state_delta": {"token": {"before": 1, "after": 2}}},
        assumptions=["N-1 block pinning", "trusted quorum"],
        policy_match_ids=["route-allow", "slippage-guard"],
    ).to_dict()

    assert outcome["assumptions"] == ["N-1 block pinning", "trusted quorum"]
    assert outcome["policy_match_ids"] == ["route-allow", "slippage-guard"]
    assert isinstance(outcome.get("state_delta_digest"), str)
    assert len(outcome["state_delta_digest"]) == 64
