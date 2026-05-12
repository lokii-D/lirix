from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig
from lirix.core.config_authority import _overlay_non_empty, resolve_config
from lirix.core.config_fingerprint import (
    fingerprint_lirix_config,
    fingerprint_registry_closure_bundle,
)
from lirix.core.evidence import (
    ExecutionEvidence,
    LayerEvidenceV2,
    SecurityTrace,
    rejected_step_to_agent_feedback,
)
from lirix.core.exceptions import (
    ConfigurationGuardException,
    HookExecutionException,
    LirixBaseException,
)
from lirix.core.session import ValidationSession, verify_replay_bundle
from lirix.layers.l3_defi_parser import DeFiPayloadParser


def _addr1() -> str:
    return "0x1111111111111111111111111111111111111111"


def _addr2() -> str:
    return "0x2222222222222222222222222222222222222222"


def test_lirix_applies_profile_fallback_update_paths() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=False,
        multicall3_address=None,
        uniswap_v2_router=None,
        chain_profile={"multicall3_address": _addr1(), "uniswap_v2_router": _addr2()},
    )
    g = Lirix(cfg)
    assert g.config.multicall3_address is not None
    assert g.config.uniswap_v2_router is not None


def test_lirix_strict_registry_validation_blocks_unlisted_addresses() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=True,
        allowed_to_addresses=[_addr1()],
        chain_profile={"protocol_registry": {"router": _addr2()}},
    )
    with pytest.raises(ConfigurationGuardException):
        Lirix(cfg)


def test_lirix_strict_registry_requires_allowlist_when_registry_addresses_present() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=True,
        allowed_to_addresses=[],
        whitelisted_addresses=[],
        chain_profile={"protocol_registry": {"router": _addr1()}},
    )
    with pytest.raises(ConfigurationGuardException) as exc_info:
        Lirix(cfg)
    assert exc_info.value.context.get("reason") == "registry_allowlist_required"


def test_lirix_strict_registry_ignores_non_address_registry_entries() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=True,
        allowed_to_addresses=[_addr1()],
        chain_profile={"protocol_registry": {"meta": "not-an-address", "allow": _addr1()}},
    )
    g = Lirix(cfg)
    assert g.config.chain_id == 1


def test_lirix_helper_methods_and_blocking_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    g = Lirix(
        LirixConfig(
            chain_id=1,
            rpc_urls=[],
            strict_mode=False,
            allowed_intents=["swap"],
            allowed_function_names=["swapExactTokensForTokens"],
            allowed_to_addresses=[_addr1()],
            whitelisted_addresses=[_addr1()],
        )
    )

    assert g._has_blocking_hook_result([{"ok": False, "failure_level": "fatal"}]) is not None
    assert (
        g._has_blocking_hook_result(
            [{"ok": False, "failure_level": "soft"}, {"ok": False, "failure_level": "fatal"}]
        )
        is not None
    )
    assert g.get_agent_resolution({"agent_feedback": {"x": 1}}) == {"x": 1}
    assert g.get_repair_instruction({"agent_feedback": {"remediation": "r"}}) == "r"
    assert g.get_repair_instruction({"agent_feedback": "bad-shape"}) == "no_repair_instruction"
    assert g.resolve_failure_protocol({}) == {}
    af = {
        "reason_code": "LIRIX_REASON_OK",
        "retry_allowed": False,
        "remediation": "x",
        "failure_type": "none",
        "layer": "L1",
    }
    fp = {
        "schema_version": "1.0",
        "failure_layer": "L1",
        "failure_type": "timeout",
        "retryable": True,
        "repair_hint": "retry",
        "human_action_required": False,
        "details": {"agent_feedback": af},
    }
    assert g.resolve_failure_protocol({"failure_protocol": fp})["reason_code"] == "LIRIX_REASON_OK"
    assert g.build_safe_payload(to=_addr1(), data="0x", function_name="fn")["function_name"] == "fn"
    assert "function_name" not in g.build_safe_payload(to=_addr1(), data="0x")

    with pytest.raises(HookExecutionException):
        g._raise_if_hook_blocked({"ok": False}, simulation=True)

    monkeypatch.setattr(
        g.hooks,
        "invoke_hooks_isolated",
        lambda *args, **kwargs: [{"ok": False, "failure_level": "fatal", "hook_point": "x"}],
    )
    with pytest.raises(HookExecutionException):
        g.chain_validate(
            "swap",
            {
                "to": _addr1(),
                "data": "0x",
                "function_name": "swapExactTokensForTokens",
            },
        )


def test_replay_api_without_sessionized_compat_wrappers() -> None:
    g = Lirix(LirixConfig(chain_id=1, rpc_urls=[], strict_mode=False))
    assert not hasattr(g, "sessionized_validate_and_simulate")
    assert not hasattr(g, "validate_only_sessionized")
    assert not hasattr(g, "simulate_only_sessionized")

    session = ValidationSession()
    session.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "c", "steps": [{"status": "ok"}]},
        status="ok",
        migration_modes={"hook_contract_mode": "legacy"},
        config_fingerprint="f" * 64,
    )
    bundle = session.replay_bundle()
    Lirix.replay_from_bundle(bundle)


def test_config_matrix_and_runtime_resolution_paths() -> None:
    with pytest.raises(ConfigurationGuardException):
        LirixConfig(
            chain_id=1,
            rpc_urls=[],
            strict_mode=True,
            decoder_plugins=[object()],
            chain_profile=None,
        )
    cfg_ok = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=False,
        hook_contract_mode="enforce",
        rpc_evidence_mode="v2_only",
    )
    assert cfg_ok.hook_contract_mode == "enforce"

    cfg, tags = resolve_config(
        config=None,
        rpc_urls=None,
        runtime_patch={"allowed_intents": ["a"], "chain_profile": {}},
    )
    assert cfg.allowed_intents == ["a"]
    assert tags["allowed_intents"] == "runtime"
    assert tags["chain_profile"] == "runtime"

    base = {"a": 1}
    tags2 = _overlay_non_empty(base, {"b": {}}, "profile")
    assert tags2 == {}
    cfg2 = LirixConfig(chain_id=1, rpc_urls=[], strict_mode=False).with_source_tags(
        {"chain_id": "preset"}
    )
    _, tags3 = resolve_config(config=cfg2, rpc_urls=None)
    assert tags3["chain_id"] == "preset"


def test_config_fingerprint_evidence_and_session_error_branches() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["https://rpc.example"],
        strict_mode=False,
        chain_profile={"k": {"z": 1}},
        allowed_intents=["swap"],
    )
    fp = fingerprint_lirix_config(cfg)
    assert isinstance(fp, str) and len(fp) == 64
    cfg_tuple = LirixConfig(
        chain_id=1,
        rpc_urls=[],
        strict_mode=False,
        chain_profile={"nested": ("a", {"b": [1, 2]})},
    )
    assert len(fingerprint_lirix_config(cfg_tuple)) == 64
    rg1 = fingerprint_registry_closure_bundle(
        chain_registry={
            "protocol_registry": {"entries": {}, "source": "a"},
            "address_registry": {"entries": {}, "source": "a"},
        },
        decoder_registry={"schema_version": "1.0", "names": ["a"]},
    )
    rg2 = fingerprint_registry_closure_bundle(
        chain_registry={
            "protocol_registry": {"entries": {}, "source": "a"},
            "address_registry": {"entries": {}, "source": "a"},
        },
        decoder_registry={"schema_version": "1.0", "names": ["a"]},
    )
    rg3 = fingerprint_registry_closure_bundle(
        chain_registry={
            "protocol_registry": {"entries": {}, "source": "b"},
            "address_registry": {"entries": {}, "source": "a"},
        },
        decoder_registry={"schema_version": "1.0", "names": ["a"]},
    )
    assert rg1 == rg2
    assert rg1 != rg3

    trace = SecurityTrace.new(correlation_id="c", intent="i", payload={"x": 1})
    trace.add_step(ExecutionEvidence(layer="L1", stage="a", status="ok"))
    trace.add_step(ExecutionEvidence(layer="L2", stage="b", status="rejected", details={"x": 1}))
    exc = LirixBaseException(error_code="E", context={"layer": "L2", "reason": "timeout"})
    fb = rejected_step_to_agent_feedback(
        trace,
        intent="i",
        correlation_id="c",
        exc=exc,
        failure_context={"layer": "L2", "reason": "timeout"},
    )
    assert fb["reason_code"] == "LIRIX_REASON_TIMEOUT"
    trace2 = SecurityTrace.new(correlation_id="c2", intent="i", payload={"x": 2})
    trace2.add_step(ExecutionEvidence(layer="L2", stage="r", status="rejected", step_id="s1"))
    fb2 = rejected_step_to_agent_feedback(
        trace2,
        intent="i",
        correlation_id="c2",
        exc=exc,
        failure_context={"layer": "L2", "reason": "timeout"},
    )
    assert fb2["details"]["step_id"] == "s1"
    trace3 = SecurityTrace.new(correlation_id="c3", intent="i", payload={"x": 3})
    trace3.add_step(ExecutionEvidence(layer="L2", stage="r", status="rejected", step_id="s2"))
    trace3.add_step(ExecutionEvidence(layer="L2", stage="ok", status="ok"))
    fb3 = rejected_step_to_agent_feedback(
        trace3,
        intent="i",
        correlation_id="c3",
        exc=exc,
        failure_context={"layer": "L2", "reason": "timeout"},
    )
    assert fb3["details"]["step_id"] == "s2"
    ev = ExecutionEvidence(layer="L1", stage="x", status="ok")
    assert "step_id" not in ev.to_dict()
    assert "reason" not in ev.to_dict()
    ev2 = ExecutionEvidence(layer="L1", stage="x", status="rejected", step_id="x", reason="r")
    assert ev2.to_dict()["step_id"] == "x"
    assert ev2.to_dict()["reason"] == "r"

    assert LayerEvidenceV2(layer="L1", status="ok", details={}).to_dict()["layer"] == "L1"

    s = ValidationSession()
    s.record_trace(
        kind="validate_only",
        trace={"trace_version": "1.0", "correlation_id": "c", "steps": [{"status": "ok"}]},
        status="ok",
    )
    s.finalize(outcome="ok")
    with pytest.raises(ConfigurationGuardException):
        s.link_trace("later")
    with pytest.raises(ConfigurationGuardException):
        s.record_event(event_type="decision", payload={"x": 1})
    with pytest.raises(ConfigurationGuardException):
        s.record_trace(
            kind="validate_only",
            trace={"trace_version": "1.0", "correlation_id": "c2", "steps": []},
            status="ok",
        )

    with pytest.raises(ConfigurationGuardException):
        verify_replay_bundle({"bundle_version": "1.0"})
    with pytest.raises(ConfigurationGuardException):
        verify_replay_bundle({"bundle_version": "2.0", "bundle_digest": "x", "payload": []})
    with pytest.raises(ConfigurationGuardException):
        verify_replay_bundle({"bundle_version": "2.0", "bundle_digest": 1, "payload": {}})
    with pytest.raises(ConfigurationGuardException):
        verify_replay_bundle(
            {"bundle_version": "2.0", "bundle_digest": "bad", "payload": {}, "migration_modes": {}}
        )


def test_session_forensic_trace_full_and_last_trace_metadata_branches() -> None:
    s = ValidationSession()
    s.timeline.append("bad-shape")
    assert s._last_trace_metadata() == {}

    s2 = ValidationSession()
    s2.record_trace(
        kind="simulate_only",
        trace={
            "trace_version": "1.0",
            "correlation_id": "c",
            "steps": [
                {"status": "ok"},
                {"status": "rejected", "details": "bad-shape"},
                {"status": "rejected", "details": {"error_code": "E1"}},
                {},
            ],
        },
        status="rejected",
        include_full_trace=True,
    )
    fb = s2.forensic_bundle()
    assert "E1" in fb["reason_codes"]
    s3 = ValidationSession()
    s3.timeline.append(
        {
            "kind": "simulate_only",
            "status": "rejected",
            "trace_summary": {"rejected_steps": 1},
            "security_trace": {"steps": [{"status": "rejected", "details": {}}]},
        }
    )
    s3.timeline.append(
        {
            "kind": "simulate_only",
            "status": "rejected",
            "trace_summary": {},
            "security_trace": {"steps": []},
        }
    )
    assert isinstance(s3.forensic_bundle()["reason_codes"], list)


def test_external_session_failure_branches_not_auto_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = Lirix(LirixConfig(chain_id=1, rpc_urls=[], strict_mode=False))
    ext = ValidationSession()

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise HookExecutionException(
            human_readable_reason="x", context={"layer": "hooks", "reason": "timeout"}
        )

    monkeypatch.setattr(g.hooks, "invoke_hooks_isolated", _boom)
    with pytest.raises(HookExecutionException):
        g.validate_and_simulate("swap", {"to": _addr1(), "data": "0x"}, session=ext)
    with pytest.raises(HookExecutionException):
        g.validate_only("swap", {"to": _addr1(), "data": "0x"}, session=ext)
    with pytest.raises(HookExecutionException):
        g.simulate_only({"to": _addr1(), "data": "0x"}, session=ext)

    async def _aboom(*args: Any, **kwargs: Any) -> Any:
        raise HookExecutionException(
            human_readable_reason="x", context={"layer": "hooks", "reason": "timeout"}
        )

    monkeypatch.setattr(g.hooks, "ainvoke_hooks_isolated", _aboom)
    import asyncio

    with pytest.raises(HookExecutionException):
        asyncio.run(
            g.async_validate_and_simulate("swap", {"to": _addr1(), "data": "0x"}, session=ext)
        )


def test_external_session_success_branches_not_auto_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    g = Lirix(LirixConfig(chain_id=1, rpc_urls=[], strict_mode=False))
    ext = ValidationSession()

    monkeypatch.setattr(
        "lirix._client_core.IntentValidator.validate", lambda self, intent, draft: True
    )
    monkeypatch.setattr("lirix._client_core.SchemaValidator.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.DeFiPayloadParser.validate", lambda self, draft: True)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_reconcile", lambda self: 1)
    monkeypatch.setattr("lirix._client_core.RPCManager.sync_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate",
        lambda self, payload, web3, block_number, state_overrides=None: {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        },
    )
    monkeypatch.setattr("lirix._client_core.RPCManager.async_reconcile", lambda self: _async_val(1))
    monkeypatch.setattr("lirix._client_core.RPCManager.async_web3", lambda self: object())
    monkeypatch.setattr(
        "lirix._client_core.SandboxSimulator.simulate_async",
        lambda self, payload, async_web3, block_number, state_overrides=None: _async_val(
            {
                "layer": "L5",
                "simulation_ok": True,
                "block_number": block_number,
                "return_data": "0x",
            }
        ),
    )

    assert "finalize" not in {
        e.get("event_type")
        for e in g.validate_only("swap", {"to": _addr1(), "data": "0x"}, session=ext)[
            "validation_session"
        ]["timeline"]
        if isinstance(e, dict) and e.get("kind") == "session_event"
    }
    assert "finalize" not in {
        e.get("event_type")
        for e in g.simulate_only({"to": _addr1(), "data": "0x"}, session=ext)["validation_session"][
            "timeline"
        ]
        if isinstance(e, dict) and e.get("kind") == "session_event"
    }
    import asyncio

    out_async = asyncio.run(
        g.async_validate_and_simulate("swap", {"to": _addr1(), "data": "0x"}, session=ext)
    )
    assert "finalize" not in {
        e.get("event_type")
        for e in out_async["validation_session"]["timeline"]
        if isinstance(e, dict) and e.get("kind") == "session_event"
    }


def _async_val(value: Any) -> Any:
    async def _inner() -> Any:
        return value

    return _inner()


def test_rejected_feedback_without_rejected_step_branch() -> None:
    trace = SecurityTrace.new(correlation_id="c4", intent="i", payload={"x": 4})
    trace.add_step(ExecutionEvidence(layer="L1", stage="ok", status="ok"))
    exc = LirixBaseException(error_code="E", context={"layer": "L1", "reason": "timeout"})
    fb = rejected_step_to_agent_feedback(
        trace,
        intent="i",
        correlation_id="c4",
        exc=exc,
        failure_context={"layer": "L1", "reason": "timeout"},
    )
    assert "step_id" not in fb["details"]


def test_l3_parser_chain_adapter_fallback_paths() -> None:
    cfg = LirixConfig(chain_id=5000, rpc_urls=[], strict_mode=False)
    guard = Lirix(
        LirixConfig(
            chain_id=5000,
            rpc_urls=[],
            strict_mode=False,
            chain_profile={"multicall3_address": _addr1(), "uniswap_v2_router": _addr2()},
        )
    )
    parser = DeFiPayloadParser(cfg, chain_adapter=guard.chain_adapter)
    assert parser._multicall() == _addr1()
    assert parser._router() == _addr2()
