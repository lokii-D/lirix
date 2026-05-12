"""Adapter-focused closure coverage for governance entrypoints."""

from __future__ import annotations

from unittest.mock import patch

import lirix
import pytest
from lirix import Lirix, build_for_chain_profile
from lirix.core.chain_adapter import ChainAdapter, build_chain_profile
from lirix.core.config import LirixConfig
from lirix.core.decoder_registry import DecoderRegistry
from lirix.core.exceptions import ConfigurationGuardException
from web3 import Web3


class _DecPlugin:
    name = "plug"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return True

    def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
        return {}


def test_build_for_chain_profile_merges_into_base_config() -> None:
    base = LirixConfig(chain_id=2, rpc_urls=[], strict_mode=False)
    guard = build_for_chain_profile(
        {"chain_id": 99, "profile_name": "merged"},
        base_config=base,
    )
    assert guard.config.chain_id == 2
    prof = guard.config.chain_profile or {}
    assert prof.get("profile_name") == "merged"


def test_replay_session_defensive_payload_fallback_under_verifier_bypass() -> None:
    with patch("lirix.core.session.verify_replay_bundle", lambda b: None):
        out = lirix.replay_session({"payload": []})
    assert out == {}


def test_protocol_and_address_registry_snapshot_optional_metadata() -> None:
    pv = ChainAdapter(
        build_chain_profile(1, {"protocol_registry": {}, "registry_version": "v-only"}),
        strict_mode=True,
    ).registry_snapshot()["protocol_registry"]
    assert pv["version"] == "v-only"
    assert "source" not in pv
    sv = ChainAdapter(
        build_chain_profile(1, {"address_registry": {}, "registry_source": "src-only"}),
        strict_mode=True,
    ).registry_snapshot()["address_registry"]
    assert sv["source"] == "src-only"
    assert "version" not in sv


def test_chain_adapter_explicit_decoder_names_branch() -> None:
    reg = DecoderRegistry()
    reg.register(_DecPlugin())
    profile = build_chain_profile(1, {"decoder_plugins": ["plug"]})
    adapter = ChainAdapter(profile, decoder_registry=reg, strict_mode=True)
    assert [p.name for p in adapter.decoder_plugins()] == ["plug"]


def test_chain_adapter_registry_snapshots_and_empty_decoder_allowlist() -> None:
    reg = DecoderRegistry()
    reg.register(_DecPlugin())
    profile = build_chain_profile(1, {"decoder_plugins": [], "decoder_policy": "compat_enable_all"})
    with pytest.raises(ConfigurationGuardException) as exc:
        ChainAdapter(profile, decoder_registry=reg, strict_mode=True)
    assert exc.value.context.get("reason") == "decoder_plugins_required"
    assert exc.value.context.get("decoder_policy") == "compat_enable_all"


def test_chain_adapter_registry_snapshots_with_explicit_decoder_allowlist() -> None:
    reg = DecoderRegistry()
    reg.register(_DecPlugin())
    profile = build_chain_profile(
        1,
        {
            "decoder_plugins": ["plug"],
            "registry_version": "rv1",
            "registry_source": "unit",
            "protocol_registry": {"p": "0x1"},
        },
    )
    adapter = ChainAdapter(profile, decoder_registry=reg, strict_mode=True)
    plugins = adapter.decoder_plugins()
    assert len(plugins) == 1
    dreg = adapter.decoder_registry_snapshot()
    assert dreg["schema_version"] == "1.0"
    snap = adapter.registry_snapshot()
    assert snap["protocol_registry"]["version"] == "rv1"
    assert snap["protocol_registry"]["source"] == "unit"
    assert "entries" in snap["address_registry"]


def test_lirix_strict_mode_registry_label_and_duplicate_and_whitespace() -> None:
    good = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=True,
        rpc_urls=["https://example.invalid"],
        whitelisted_addresses=[good],
        chain_profile={
            "protocol_registry": {" ": good},
        },
    )
    with pytest.raises(ConfigurationGuardException) as exc:
        Lirix(config=cfg)
    assert exc.value.context.get("reason") == "registry_label_invalid"

    cfg2 = LirixConfig(
        chain_id=1,
        strict_mode=True,
        rpc_urls=["https://example.invalid"],
        whitelisted_addresses=[good],
        chain_profile={"protocol_registry": {"a b": good}},
    )
    with pytest.raises(ConfigurationGuardException) as exc2:
        Lirix(config=cfg2)
    assert exc2.value.context.get("reason") == "registry_label_whitespace"

    cfg3 = LirixConfig(
        chain_id=1,
        strict_mode=True,
        rpc_urls=["https://example.invalid"],
        whitelisted_addresses=[good],
        chain_profile={"protocol_registry": {"Router": good, "router": good}},
    )
    with pytest.raises(ConfigurationGuardException) as exc3:
        Lirix(config=cfg3)
    assert exc3.value.context.get("reason") == "registry_label_duplicate"
