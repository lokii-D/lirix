# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_invoke_guardian_plain_string_result_policy_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        captured["intent"] = intent
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"], default_intent="swap", security_policy={"base": 1}
    )
    out = tool._run("swap 1 ETH for USDC", security_policy={"override": 2}, extra=True)
    assert out == "ok"
    assert captured["intent"] == "swap"
    assert captured["payload"]["raw_intent_or_calldata"] == "swap 1 ETH for USDC"
    assert captured["payload"]["extra"] is True
    assert captured["kwargs"]["security_policy"] == {"base": 1, "override": 2}


def test_test_langchain_tool_invoke_guardian_plain_string_result_policy_merge_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return "ok-async"

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    assert pytest.importorskip("asyncio")
    import asyncio

    assert asyncio.run(tool._arun("swap 1 ETH for USDC")) == "ok-async"
