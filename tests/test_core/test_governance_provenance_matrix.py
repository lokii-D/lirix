from __future__ import annotations

from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config


def test_provenance_chain_present_in_resolved_config_tags_for_inferred_branch() -> None:
    cfg, tags = resolve_config(
        config=None,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["swap"], "chain_profile": {}},
    )
    assert tags["__provenance_chain__"] == "inferred>runtime_patch"
    assert "config:inferred" in tags["__provenance_decisions__"]
    assert "patch:runtime_applied" in tags["__provenance_decisions__"]
    assert cfg.config_source_tags["__provenance_chain__"] == "inferred>runtime_patch"


def test_provenance_chain_present_in_resolved_config_tags_for_explicit_branch() -> None:
    base = LirixConfig(chain_id=1, rpc_urls=["https://rpc.example"], strict_mode=False)
    cfg, tags = resolve_config(
        config=base,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["swap"]},
    )
    assert tags["__provenance_chain__"] == "explicit>profile>inferred>runtime_patch"
    assert "config:explicit" in tags["__provenance_decisions__"]
    assert "defaults:profile_overlay" in tags["__provenance_decisions__"]
    assert cfg.config_source_tags["__provenance_chain__"] == "explicit>profile>inferred>runtime_patch"


def test_governance_snapshot_exposes_stable_config_source_tags_matrix() -> None:
    base = LirixConfig(
        chain_id=1,
        rpc_urls=["https://rpc.example"],
        strict_mode=False,
        runtime_patch_allowlist=["allowed_intents"],
    )
    client = Lirix(
        config=base,
        runtime_patch={"allowed_intents": ["swap"], "chain_profile": {"custom": "x"}},
    )
    snap = client._governance_snapshot()
    tags = snap["config_source_tags"]
    assert tags["__provenance_chain__"] == "explicit>profile>inferred>runtime_patch"
    assert "validate:model" in tags["__provenance_decisions__"]
    assert tags["allowed_intents"] == "runtime"
