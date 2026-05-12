from __future__ import annotations

import asyncio

import pytest
from lirix import Lirix, replay_session
from lirix.core.session import verify_replay_bundle


def _install_success_monkeypatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())

    async def _async_reconcile(self) -> int:  # type: ignore[no-untyped-def]
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _async_reconcile)
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        },
    )

    async def _simulate_async(self, payload, async_web3, block_number, state_overrides=None):  # type: ignore[no-untyped-def]
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr("lirix._client_core.SandboxSimulator.simulate_async", _simulate_async)


def test_replay_closure_parity_validate_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    out = guard.validate_only("swap", {"to": "0x1", "data": "0x"})
    rb = out["replay_bundle"]
    assert rb.get("registry_closure_digest")
    assert "replay_proof" in rb
    assert "ext_resolved_decoder_plugins_digest" in (rb.get("artifact_digests") or {})
    verify_replay_bundle(rb, enforce_replay_proof_strict=True)
    replay_session(rb, enforce_replay_proof_strict=True)


def test_replay_closure_parity_simulate_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    out = guard.simulate_only({"to": "0x1", "data": "0x"})
    rb = out["replay_bundle"]
    assert rb.get("registry_closure_digest")
    assert "ext_resolved_decoder_plugins_digest" in (rb.get("artifact_digests") or {})
    verify_replay_bundle(rb, enforce_replay_proof_strict=True)


def test_replay_closure_parity_validate_and_simulate(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    out = guard.validate_and_simulate("swap", {"to": "0x1", "data": "0x"})
    rb = out["replay_bundle"]
    assert rb.get("registry_closure_digest")
    assert "ext_resolved_decoder_plugins_digest" in (rb.get("artifact_digests") or {})
    verify_replay_bundle(rb, enforce_replay_proof_strict=True)


def test_replay_closure_parity_async_validate_and_simulate(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_success_monkeypatches(monkeypatch)
    guard = Lirix(rpc_urls=["https://example.invalid"])
    out = asyncio.run(guard.async_validate_and_simulate("swap", {"to": "0x1", "data": "0x"}))
    rb = out["replay_bundle"]
    assert rb.get("registry_closure_digest")
    assert "ext_resolved_decoder_plugins_digest" in (rb.get("artifact_digests") or {})
    verify_replay_bundle(rb, enforce_replay_proof_strict=True)
