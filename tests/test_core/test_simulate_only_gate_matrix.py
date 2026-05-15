# SPDX-License-Identifier: MIT
"""Matrix: simulate_only gate + sync/async entrypoints stay aligned (regression vs run_full re-check)."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Literal

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_POST_VALIDATE, HOOK_PRE_VALIDATE
from lirix.core.exceptions import (
    ConfigurationGuardException,
    HookExecutionException,
    SchemaValidationException,
)
from lirix.core.session import ValidationSession

from tests.test_core.test_replay_registry_closure_parity_all_entrypoints import (
    _install_success_monkeypatches,
)
from tests.test_core.test_simulate_only_gate_semantics import _minimal_swap_payload
from tests.test_core.test_simulate_only_prior_validate_config import _gate_cfg

Entry = Literal["sync", "async"]


def _cfg_no_gate() -> LirixConfig:
    return LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=["https://example.invalid"],
        simulate_only_requires_prior_validate=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )


async def _simulate_only(
    client: Lirix, payload: dict[str, object], session: ValidationSession | None
) -> dict[str, Any]:
    return await client.async_simulate_only(payload, session=session)


def _simulate_only_sync(
    client: Lirix, payload: dict[str, object], session: ValidationSession | None
) -> dict[str, Any]:
    return client.simulate_only(payload, session=session)


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_false_gate_explicit_none_session_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_cfg_no_gate())
    p = _minimal_swap_payload()
    if entry == "sync":
        out = _simulate_only_sync(client, p, None)
    else:
        out = asyncio.run(_simulate_only(client, p, None))
    assert out.get("simulation_ok") is True


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_external_session_without_flag_blocks_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()

    def _expect_block(run: Callable[[], None]) -> None:
        with pytest.raises(ConfigurationGuardException) as ei:
            run()
        assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"

    if entry == "sync":
        _expect_block(lambda: _simulate_only_sync(client, p, sess))
    else:
        _expect_block(lambda: asyncio.run(_simulate_only(client, p, sess)))


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_after_validate_only_success_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    _install_success_monkeypatches(monkeypatch)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()
    client.validate_only("swap", p, session=sess)
    assert sess.state.get("l1_l3_ok") is True
    if entry == "sync":
        out = _simulate_only_sync(client, p, sess)
    else:
        out = asyncio.run(_simulate_only(client, p, sess))
    assert out.get("simulation_ok") is True


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_after_full_pipeline_recheck_failure_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    _install_success_monkeypatches(monkeypatch)
    n = {"c": 0}
    orig = Lirix._run_l1_l3_validation

    def _wrapped(self: Lirix, **kw: Any) -> None:
        n["c"] += 1
        if n["c"] == 2:
            raise SchemaValidationException(
                human_readable_reason="matrix recheck",
                context={"reason": "schema_recheck_matrix"},
            )
        return orig(self, **kw)

    monkeypatch.setattr("lirix._facade.Lirix._run_l1_l3_validation", _wrapped)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()
    with pytest.raises(SchemaValidationException):
        client.validate_and_simulate("swap", p, session=sess)
    assert n["c"] == 2
    assert sess.state.get("l1_l3_ok") is True
    if entry == "sync":
        out = _simulate_only_sync(client, p, sess)
    else:
        out = asyncio.run(_simulate_only(client, p, sess))
    assert out.get("simulation_ok") is True


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_after_async_full_pipeline_recheck_failure_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    """Same as sync full pipeline re-check failure, but entry is async_validate_and_simulate."""
    _install_success_monkeypatches(monkeypatch)
    n = {"c": 0}
    orig = Lirix._run_l1_l3_validation

    def _wrapped(self: Lirix, **kw: Any) -> None:
        n["c"] += 1
        if n["c"] == 2:
            raise SchemaValidationException(
                human_readable_reason="matrix async recheck",
                context={"reason": "schema_recheck_matrix_async"},
            )
        return orig(self, **kw)

    monkeypatch.setattr("lirix._facade.Lirix._run_l1_l3_validation", _wrapped)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()
    with pytest.raises(SchemaValidationException):
        asyncio.run(client.async_validate_and_simulate("swap", p, session=sess))
    assert n["c"] == 2
    assert sess.state.get("l1_l3_ok") is True
    if entry == "sync":
        out = _simulate_only_sync(client, p, sess)
    else:
        out = asyncio.run(_simulate_only(client, p, sess))
    assert out.get("simulation_ok") is True


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_validate_only_blocked_post_validate_simulate_blocks_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    _install_success_monkeypatches(monkeypatch)

    async def _ahook(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        if hp == HOOK_POST_VALIDATE and str(kwargs.get("intent", "")) != "simulate_only":
            return [{"ok": False, "failure_level": "fatal", "reason": "matrix_post_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ahook)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()
    with pytest.raises(HookExecutionException):
        client.validate_only("swap", p, session=sess)
    assert sess.state.get("l1_l3_ok") is not True

    def _expect_block() -> None:
        with pytest.raises(ConfigurationGuardException) as ei:
            if entry == "sync":
                _simulate_only_sync(client, p, sess)
            else:
                asyncio.run(_simulate_only(client, p, sess))
        assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"

    _expect_block()


@pytest.mark.parametrize("entry", ("sync", "async"))
def test_matrix_true_gate_validate_only_blocked_pre_validate_simulate_blocks_parity(
    monkeypatch: pytest.MonkeyPatch, entry: Entry
) -> None:
    """Different failure point: HOOK_PRE_VALIDATE blocks before L1–L3 completes → gate never set."""
    _install_success_monkeypatches(monkeypatch)

    async def _ahook(self: Any, hp: str, **kwargs: Any) -> list[dict[str, Any]]:
        if hp == HOOK_PRE_VALIDATE and str(kwargs.get("intent", "")) == "swap":
            return [{"ok": False, "failure_level": "fatal", "reason": "matrix_pre_block"}]
        return []

    monkeypatch.setattr("lirix._client_core.HookManager.ainvoke_hooks_isolated", _ahook)
    client = Lirix(_gate_cfg())
    sess = ValidationSession(workflow_mode="direct")
    p = _minimal_swap_payload()
    with pytest.raises(HookExecutionException):
        client.validate_only("swap", p, session=sess)
    assert sess.state.get("l1_l3_ok") is not True

    with pytest.raises(ConfigurationGuardException) as ei:
        if entry == "sync":
            _simulate_only_sync(client, p, sess)
        else:
            asyncio.run(_simulate_only(client, p, sess))
    assert ei.value.context.get("reason") == "simulate_only_prior_validate_required"
