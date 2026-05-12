from __future__ import annotations

from lirix import Lirix
from lirix.core.chain_adapter import ChainAdapter, build_chain_profile
from lirix.core.decoder_registry import DecoderRegistry


class _NoopPlugin:
    name = "noop"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return False

    def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
        return {}


def test_chain_adapter_resolves_protocol_and_address_registries() -> None:
    registry = DecoderRegistry()
    registry.register(_NoopPlugin())
    profile = build_chain_profile(
        1,
        {
            "protocol_registry": {"uniswap_v3_router": "0x111"},
            "address_registry": {"usdc": "0x222"},
            "simulation_backend_profile": {"provider": "anvil", "mode": "fork", "fork_block": 123},
            "decoder_plugins": ["noop"],
        },
    )
    adapter = ChainAdapter(profile, decoder_registry=registry)
    assert adapter.resolve_protocol_address("uniswap_v3_router") == "0x111"
    assert adapter.resolve_registered_address("USDC") == "0x222"
    backend = adapter.simulation_backend_profile()
    assert backend["provider"] == "anvil"
    assert backend["mode"] == "fork"
    assert backend["metadata"]["fork_block"] == 123


def test_chain_profile_runtime_policies_are_consumed_by_l4_l5_builders() -> None:
    guard = Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={
            "chain_profile": {
                "rpc_policy": {"request_timeout": 7},
                "simulation_backend_profile": {"provider": "anvil", "mode": "fork"},
            }
        },
    )
    rpc = guard._build_rpc_manager()
    sim = guard._build_sandbox_simulator()
    assert rpc._timeout == 7
    result = sim._build_result(block_number=1, result=b"")
    assert result["backend_profile"]["provider"] == "anvil"


def test_chain_profile_partitions_unknown_rpc_policy_keys_into_metadata() -> None:
    profile = build_chain_profile(
        1,
        {"rpc_policy": {"request_timeout": 9, "unknown_rpc_toggle": True}},
    )
    assert profile.rpc_policy == {"request_timeout": 9}
    assert profile.metadata.get("rpc_policy_extra") == {"unknown_rpc_toggle": True}


def test_chain_profile_merges_unknown_rpc_keys_with_explicit_rpc_policy_extra() -> None:
    profile = build_chain_profile(
        1,
        {
            "rpc_policy": {"legacy_opt": 1},
            "rpc_policy_extra": {"already": "x"},
        },
    )
    assert profile.rpc_policy == {}
    assert profile.metadata.get("rpc_policy_extra") == {"already": "x", "legacy_opt": 1}


def test_resolved_decoder_digest_matches_when_allowlist_equals_compat_resolution() -> None:
    baseline = Lirix(rpc_urls=["https://example.invalid"])
    resolved = baseline._resolved_decoder_plugins()
    chain_patch: dict[str, object] = {"decoder_plugins": resolved}
    # Empty allowlist + default profile policy is invalid; mirror explicit_only semantics for [].
    if not resolved:
        chain_patch["decoder_policy"] = "explicit_only"
    explicit = Lirix(
        rpc_urls=["https://example.invalid"],
        runtime_patch={"chain_profile": chain_patch},
    )
    assert (
        baseline._resolved_decoder_plugins_digest() == explicit._resolved_decoder_plugins_digest()
    )
    assert baseline._resolved_decoder_plugins() == explicit._resolved_decoder_plugins()
    if resolved:
        assert explicit._decoder_mode() == "profile_allowlist"
