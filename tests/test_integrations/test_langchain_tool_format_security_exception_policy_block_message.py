# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


def test_test_langchain_tool_format_security_exception_policy_block_message() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="abort now",
        context={"policy_key": "max_slippage_bps", "expected": 50, "observed": 250},
    )
    assert "max_slippage_bps violated" in _format_security_exception(exc)


def test_test_langchain_tool_format_security_exception_policy_block_message_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return "ok"

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    assert asyncio.run(tool._arun("swap 1 ETH for USDC")) == "ok"
