from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config
from lirix.core.exceptions import ConfigurationGuardException


def test_resolve_config_uses_profile_defaults_without_overriding_explicit() -> None:
    cfg = LirixConfig(
        chain_id=5000,
        rpc_urls=["https://rpc.custom"],
        multicall3_address=None,
        uniswap_v2_router="0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
        chain_profile={
            "multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11",
            "uniswap_v2_router": "0x6e3d7b0365c960aaf214e0afa86a99b4a62ae82d",
        },
        strict_mode=False,
    )
    resolved, tags = resolve_config(config=cfg, rpc_urls=None)
    assert resolved.multicall3_address == "0xcA11bde05977b3631167028862bE2a173976CA11"
    assert resolved.uniswap_v2_router == "0xeaEE7EE68874218c3558b40063c42B82D3E7232a"
    assert tags["multicall3_address"] == "profile"


def test_resolve_config_profile_defaults_fill_both_missing_targets() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://rpc.custom"],
        multicall3_address=None,
        uniswap_v2_router=None,
        chain_profile={
            "multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11",
            "uniswap_v2_router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        },
        strict_mode=False,
    )
    resolved, tags = resolve_config(config=cfg, rpc_urls=None)
    assert resolved.multicall3_address == "0xcA11bde05977b3631167028862bE2a173976CA11"
    assert resolved.uniswap_v2_router == "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    assert tags["multicall3_address"] == "profile"
    assert tags["uniswap_v2_router"] == "profile"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("multicall3_address", "not_an_address"),
        ("uniswap_v2_router", "not_an_address"),
    ],
)
def test_resolve_config_chain_profile_fallback_revalidation_fail_closed(
    field: str, value: str
) -> None:
    profile = {field: value}
    cfg = LirixConfig(
        chain_id=1, rpc_urls=["https://rpc.example"], strict_mode=False, chain_profile=profile
    )
    with pytest.raises(ConfigurationGuardException):
        resolve_config(config=cfg, rpc_urls=None)


def test_strict_mode_rejects_protected_runtime_patch_allowlist_overlap() -> None:
    with pytest.raises(ConfigurationGuardException) as exc_info:
        LirixConfig(
            chain_id=1,
            rpc_urls=["https://rpc.example"],
            strict_mode=True,
            rpc_evidence_mode="v2_only",
            policy_lifecycle_mode="digest_verified",
            runtime_patch_allowlist=["rpc_evidence_mode"],
        )
    assert exc_info.value.context.get("reason") == "runtime_patch_allowlist_protected_overlap"


def test_resolve_config_runtime_patch_tags_source() -> None:
    cfg = LirixConfig(chain_id=1, rpc_urls=["https://a"], strict_mode=False)
    resolved, tags = resolve_config(
        config=cfg, rpc_urls=None, runtime_patch={"allowed_intents": ["x"]}
    )
    assert resolved.allowed_intents == ["x"]
    assert tags.get("allowed_intents") == "runtime"


def test_resolve_config_runtime_patch_override_requires_allowlist() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://a"],
        strict_mode=False,
        allowed_intents=["explicit"],
    )
    resolved, tags = resolve_config(
        config=cfg,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["runtime"]},
    )
    assert resolved.allowed_intents == ["explicit"]
    assert tags.get("allowed_intents") != "runtime_override"


def test_resolve_config_runtime_patch_override_works_with_allowlist() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://a"],
        strict_mode=False,
        allowed_intents=["explicit"],
        runtime_patch_allowlist=["allowed_intents"],
    )
    resolved, tags = resolve_config(
        config=cfg,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["runtime"]},
    )
    assert resolved.allowed_intents == ["runtime"]
    assert tags.get("allowed_intents") == "runtime_override"


def test_resolve_config_runtime_patch_override_forbidden_in_strict_mode() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://a"],
        strict_mode=True,
        allowed_intents=["explicit"],
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        resolve_config(
            config=cfg,
            rpc_urls=None,
            runtime_patch={"allowed_intents": ["runtime"]},
        )
    assert exc_info.value.context.get("reason") == "runtime_patch_override_forbidden"
    assert exc_info.value.context.get("field") == "allowed_intents"


@pytest.mark.parametrize(
    ("kwargs", "expected_reason"),
    [
        pytest.param(
            {
                "rpc_evidence_mode": "v2_only",
                "policy_lifecycle_mode": "digest_verified",
                "blacklisted_addresses": ["0x0000000000000000000000000000000000000001"],
                "whitelisted_addresses": ["0x0000000000000000000000000000000000000001"],
                "allowed_to_addresses": ["0x0000000000000000000000000000000000000001"],
            },
            "overlap_blacklist_whitelist",
            id="overlap-prioritized-over-stack-modes",
        ),
        pytest.param(
            {
                "rpc_evidence_mode": "v2_only",
                "policy_lifecycle_mode": "digest_verified",
                "blacklisted_addresses": ["0x0000000000000000000000000000000000000001"],
                "whitelisted_addresses": [],
                "allowed_to_addresses": ["0x0000000000000000000000000000000000000001"],
            },
            "overlap_blacklist_allowed_to",
            id="allowed_to-overlap-prioritized-over-stack-modes",
        ),
    ],
)
def test_strict_mode_conflict_priority_is_stable_for_multi_conflict_input(
    kwargs: dict[str, object], expected_reason: str
) -> None:
    with pytest.raises(ConfigurationGuardException) as exc_info:
        LirixConfig(
            chain_id=1,
            rpc_urls=["https://rpc.example"],
            strict_mode=True,
            **kwargs,
        )
    assert exc_info.value.context.get("reason") == expected_reason
