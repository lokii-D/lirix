# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException, RPCUnavailableException
from lirix.core.session import ValidationSession

from tests.test_core.test_replay_registry_closure_parity_all_entrypoints import (
    _install_success_monkeypatches,
)


def test_simulate_only_requires_prior_validate_blocks_without_session_flag() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        simulate_only_requires_prior_validate=True,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )
    client = Lirix(cfg)
    with pytest.raises(ConfigurationGuardException) as ei:
        client.simulate_only({"to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "data": "0x"})
    assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"


def test_validate_only_marks_session_l1_l3_ok_for_simulate_gate() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        simulate_only_requires_prior_validate=True,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )
    client = Lirix(cfg)
    sess = ValidationSession()
    client.validate_only(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": "0x",
        },
        session=sess,
    )
    assert sess.state.get("l1_l3_ok") is True


def _gate_cfg() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=["https://example.invalid"],
        simulate_only_requires_prior_validate=True,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


def test_validate_and_simulate_marks_l1_l3_ok_then_simulate_only_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession()
    payload = {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }
    client.validate_and_simulate("swap", payload, session=sess)
    assert sess.state.get("l1_l3_ok") is True
    out = client.simulate_only(payload, session=sess)
    assert out.get("simulation_ok") is True


def test_validate_and_simulate_l4_failure_after_l3_keeps_l1_l3_ok_simulate_gate_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Governance: gate reflects L1–L3 success even if full pipeline aborts before POST_VALIDATE."""
    _install_success_monkeypatches(monkeypatch)

    calls = {"n": 0}

    def _boom_once_then_ok(self):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise RPCUnavailableException(context={"reason": "patched_post_l3"})
        return 1

    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", _boom_once_then_ok)

    async def _boom_once_then_ok_async(self: object) -> int:
        return _boom_once_then_ok(self)

    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", _boom_once_then_ok_async)
    client = Lirix(_gate_cfg())
    sess = ValidationSession()
    payload = {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }
    with pytest.raises(RPCUnavailableException):
        client.validate_and_simulate("swap", payload, session=sess)
    assert sess.state.get("l1_l3_ok") is True
    out = client.simulate_only(payload, session=sess)
    assert out.get("simulation_ok") is True


@pytest.mark.asyncio
async def test_async_validate_and_simulate_marks_l1_l3_ok_then_simulate_only_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession()
    payload = {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }
    await client.async_validate_and_simulate("swap", payload, session=sess)
    assert sess.state.get("l1_l3_ok") is True
    out = client.simulate_only(payload, session=sess)
    assert out.get("simulation_ok") is True
