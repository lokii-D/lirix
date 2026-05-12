# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix import Lirix
from lirix.core.config_fingerprint import fingerprint_registry_closure_bundle


def test_replay_bundle_registry_closure_digest_matches_runtime_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = Lirix(rpc_urls=["https://example.invalid"])
    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)

    out = g.validate_only("swap", {"to": "0x1", "data": "0x"})
    rb = out["replay_bundle"]
    assert rb.get("registry_closure_digest")

    expected = fingerprint_registry_closure_bundle(
        chain_registry=g.chain_adapter.registry_snapshot(),
        decoder_registry=g.chain_adapter.decoder_registry_snapshot(),
    )
    assert rb["registry_closure_digest"] == expected


def test_forensic_bundle_captures_agent_reason_codes_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = Lirix(rpc_urls=["https://example.invalid"])

    def _raise(*args: object, **kwargs: object) -> None:
        # Using existing exception adapter path.
        from lirix.core.exceptions import InvalidIntentException

        raise InvalidIntentException(
            human_readable_reason="timed out",
            context={"layer": "L1", "reason": "timeout"},
        )

    monkeypatch.setattr("lirix._client_core.IntentValidator.validate", _raise)

    with pytest.raises(Exception) as exc_info:
        g.validate_only("swap", {"to": "0x1", "data": "0x"})
    ctx = getattr(exc_info.value, "context", {})
    fb = ctx.get("forensic_bundle", {})
    assert isinstance(fb.get("agent_reason_codes"), list)
    assert "LIRIX_REASON_TIMEOUT" in fb.get("agent_reason_codes", [])
