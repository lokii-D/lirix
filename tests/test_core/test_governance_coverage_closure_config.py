"""Config-focused closure coverage for governance entrypoints."""

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config


def test_resolve_config_none_with_runtime_chain_profile() -> None:
    resolved, tags = resolve_config(
        config=None,
        rpc_urls=None,
        runtime_patch={"chain_profile": {"chain_id": 7, "profile_name": "rp"}},
    )
    assert resolved.chain_profile is not None
    assert tags.get("chain_profile") == "runtime"


def test_resolve_config_explicit_chain_profile_runtime_special_case_empty_mapping() -> None:
    """Overlay skips empty dict values; explicit branch still pins chain_profile."""
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://a"],
        chain_profile=None,
        strict_mode=False,
    )
    resolved, tags = resolve_config(
        config=cfg,
        rpc_urls=None,
        runtime_patch={"chain_profile": {}},
    )
    assert resolved.chain_profile == {}
    assert tags.get("chain_profile") == "runtime"
