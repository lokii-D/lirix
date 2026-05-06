# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_invoke_guardian_uses_default_intent_stringifies_plain_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        captured["intent"] = intent
        captured["payload"] = payload
        return 123

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="transfer")
    assert tool._run("send 1 token") == "123"
    assert captured["intent"] == "transfer"
    assert captured["payload"]["raw_intent_or_calldata"] == "send 1 token"
