# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from lirix.core.exceptions import LirixPolicyViolationException, LirixSecurityException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


class _Model:
    def model_dump_json(self) -> str:
        return '{"ok": true}'


def test_test_langchain_tool_format_security_exception_policy_context() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="blocked",
        context={"policy_key": "max_slippage_bps", "expected": 1, "observed": 2},
    )
    msg = _format_security_exception(exc)
    assert "max_slippage_bps violated" in msg
    assert "blocked" in msg


def test_test_langchain_tool_format_security_exception_policy_context_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        calls.append(intent)
        return _Model()

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    sync_out = json.loads(tool._run("swap 1 ETH for USDC"))
    assert sync_out["ok"] is True
    assert sync_out["tx_payload"] == {"to": None, "data": None, "value": 0}
    async_out = json.loads(asyncio.run(tool._arun("swap 1 ETH for USDC")))
    assert async_out["ok"] is True
    assert async_out["tx_payload"] == {"to": None, "data": None, "value": 0}
    assert calls == ["swap", "swap"]


def test_test_langchain_tool_format_security_exception_policy_context_3() -> None:
    exc = LirixSecurityException(resolution_agent="use another route")
    assert _format_security_exception(exc) == "use another route"
