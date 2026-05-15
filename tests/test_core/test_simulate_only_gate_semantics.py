# SPDX-License-Identifier: MIT
"""Regression: simulate_only gate semantics stay stable alongside run_full L1–L3 re-check (no extra L1–L3)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_POST_VALIDATE
from lirix.core.exceptions import (
    ConfigurationGuardException,
    HookExecutionException,
    SchemaValidationException,
)
from lirix.core.session import ValidationSession

from tests.test_core.test_replay_registry_closure_parity_all_entrypoints import (
    _install_success_monkeypatches,
)
from tests.test_core.test_simulate_only_prior_validate_config import _gate_cfg


def _minimal_swap_payload() -> dict[str, object]:
    return {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }


def test_simulate_only_default_config_no_prior_validate_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh session + default config: simulate_only is unchanged (L4–L5 only, no L1–L3 revalidation path)."""
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=["https://example.invalid"],
            simulate_only_requires_prior_validate=False,
            allowed_intents=["swap"],
            allowed_function_names=["swapExactTokensForTokens"],
            allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
            whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        )
    )
    out = client.simulate_only(_minimal_swap_payload())
    assert out.get("simulation_ok") is True


def test_simulate_only_with_l1_l3_ok_session_still_enters_l4_l5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate satisfied: prior validate marks l1_l3_ok; simulate_only still succeeds (not perturbed by run_full DAG)."""
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    payload = _minimal_swap_payload()
    client.validate_only("swap", payload, session=sess)
    assert sess.state.get("l1_l3_ok") is True
    out = client.simulate_only(payload, session=sess)
    assert out.get("simulation_ok") is True


def test_simulate_only_gate_blocks_without_l1_l3_ok_when_required() -> None:
    """Gate enforced: empty session + require prior validate still fails closed (unchanged contract)."""
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
        client.simulate_only(_minimal_swap_payload())
    assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"


def test_simulate_only_false_gate_explicit_none_session_sync_and_async(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """simulate_only_requires_prior_validate=False: explicit session=None is still L4–L5-only (sync + async)."""
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(
        LirixConfig(
            chain_id=1,
            strict_mode=False,
            rpc_urls=["https://example.invalid"],
            simulate_only_requires_prior_validate=False,
            allowed_intents=["swap"],
            allowed_function_names=["swapExactTokensForTokens"],
            allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
            whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        )
    )
    payload = _minimal_swap_payload()
    sync_out = client.simulate_only(payload, session=None)
    assert sync_out.get("simulation_ok") is True
    async_out = asyncio.run(client.async_simulate_only(payload, session=None))
    assert async_out.get("simulation_ok") is True


def test_simulate_only_gate_true_external_session_without_l1_l3_ok_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gate is keyed only on state['l1_l3_ok'], not merely 'a session object exists'."""
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    with pytest.raises(ConfigurationGuardException) as ei:
        client.simulate_only(_minimal_swap_payload(), session=sess)
    assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"
    assert sess.state.get("l1_l3_ok") is not True


def test_simulate_only_after_full_pipeline_recheck_failure_l1_l3_ok_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full pipeline fails at post–pre_simulation L1–L3 re-check; simulate_only gate still sees initial L1–L3 ok."""
    _install_success_monkeypatches(monkeypatch)
    state = {"n": 0}
    orig = Lirix._run_l1_l3_validation

    def _wrapped(self: Lirix, **kw: Any) -> None:
        state["n"] += 1
        if state["n"] == 2:
            raise SchemaValidationException(
                human_readable_reason="post pre_sim re-check",
                context={"reason": "schema_recheck_gate_matrix"},
            )
        return orig(self, **kw)

    monkeypatch.setattr("lirix._facade.Lirix._run_l1_l3_validation", _wrapped)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    payload = _minimal_swap_payload()
    with pytest.raises(SchemaValidationException):
        client.validate_and_simulate("swap", payload, session=sess)
    assert state["n"] == 2
    assert sess.state.get("l1_l3_ok") is True
    out = client.simulate_only(payload, session=sess)
    assert out.get("simulation_ok") is True


def test_simulate_only_gate_requires_completed_validate_only_not_partial_l1_l3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If validate_only never reaches _mark_session_l1_l3_ok (hook blocks after L1–L3), simulate_only must still block."""
    _install_success_monkeypatches(monkeypatch)

    async def _ahook(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        if hp == HOOK_POST_VALIDATE and str(kwargs.get("intent", "")) != "simulate_only":
            return [
                {"ok": False, "failure_level": "fatal", "reason": "contract_post_validate_block"}
            ]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ahook)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    with pytest.raises(HookExecutionException):
        client.validate_only("swap", _minimal_swap_payload(), session=sess)
    assert sess.state.get("l1_l3_ok") is not True
    with pytest.raises(ConfigurationGuardException) as ei:
        client.simulate_only(_minimal_swap_payload(), session=sess)
    assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"
