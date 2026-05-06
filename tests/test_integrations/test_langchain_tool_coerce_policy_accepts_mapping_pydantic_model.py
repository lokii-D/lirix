# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.core.exceptions import LirixPolicyViolationException, LirixSecurityException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model() -> None:
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    assert tool._coerce_policy(None) == {}
    assert tool._coerce_policy({"a": 1}) == {"a": 1}

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, int]:
            return {"b": 2}

    assert tool._coerce_policy(_Model()) == {"b": 2}
    with pytest.raises(TypeError, match="policy must be a mapping or Pydantic model"):
        tool._coerce_policy(1)


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model_2() -> None:
    exc = LirixSecurityException(resolution_agent="use another route")
    assert _format_security_exception(exc) == "use another route"


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model_3() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="stop",
        context={"policy_key": "slippage", "expected": 1, "observed": 3},
    )
    assert _format_security_exception(exc) == (
        "Transaction Blocked by Lirix Policy: slippage violated (expected=1, observed=3). stop"
    )


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        captured["intent"] = intent
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"ok": True}

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"],
        default_intent="swap",
        state_delta_assertions={"expected": 1},
        security_policy={"policy": "base"},
    )

    result = tool._run(
        "swap 1 ETH for USDC",
        state_delta_assertions={"override": 2},
        security_policy={"policy": "override"},
        extra_flag=True,
    )

    assert result == "{'ok': True}"
    assert captured["intent"] == "swap"
    assert captured["payload"]["raw_intent_or_calldata"] == "swap 1 ETH for USDC"
    assert captured["payload"]["expected"] == 1
    assert captured["payload"]["override"] == 2
    assert captured["payload"]["extra_flag"] is True
    assert captured["kwargs"]["security_policy"] == {"policy": "override"}


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model_5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class PolicyModel:
        def model_dump(self, mode: str = "python") -> dict[str, str]:
            return {"from_model": mode}

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return "done"

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"],
        security_policy=PolicyModel(),
        state_delta_assertions={"base": "yes"},
    )

    assert tool._security_policy == {"from_model": "python"}
    assert tool._run("raw", security_policy={"override": True}) == "done"
    assert captured["payload"]["base"] == "yes"
    assert captured["kwargs"]["security_policy"] == {"from_model": "python", "override": True}


def test_test_langchain_tool_coerce_policy_accepts_mapping_pydantic_model_6() -> None:
    with pytest.raises(TypeError, match="policy must be a mapping or Pydantic model"):
        LirixSecurityValidator(rpc_urls=["https://example.invalid"], policy=object())


@pytest.mark.asyncio
async def test_validator_async_path_serializes_model_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Dummy:
        def model_dump_json(self) -> str:
            return '{"async": true}'

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return Dummy()

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    output = await tool._arun("swap 1 ETH for USDC")
    assert output == '{"async": true}'
