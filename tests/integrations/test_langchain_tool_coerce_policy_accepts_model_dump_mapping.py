# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


def test_test_langchain_tool_coerce_policy_accepts_model_dump_mapping() -> None:
    class _P:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"a": 1}

    assert LirixSecurityValidator._coerce_policy({"x": 2}) == {"x": 2}
    assert LirixSecurityValidator._coerce_policy(_P()) == {"a": 1}


def test_test_langchain_tool_coerce_policy_accepts_model_dump_mapping_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        observed.update({"intent": intent, "payload": payload, "kwargs": kwargs})

        class _R:
            def model_dump_json(self) -> str:
                return '{"ok": true}'

        return _R()

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(
        rpc_urls=["https://rpc.invalid"],
        default_intent="swap",
        state_delta_assertions={"a": 1},
        security_policy={"policy": "base"},
    )
    out = tool._run("payload", state_delta_assertions={"b": 2}, extra=3)
    assert out == '{"ok": true}'
    assert observed["intent"] == "swap"
    assert observed["payload"]["raw_intent_or_calldata"] == "payload"
    assert observed["payload"]["a"] == 1
    assert observed["payload"]["b"] == 2
    assert observed["payload"]["extra"] == 3
    assert observed["kwargs"]["security_policy"] == {"policy": "base"}


def test_test_langchain_tool_coerce_policy_accepts_model_dump_mapping_3() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="blocked",
        context={"policy_key": "max_slippage_bps", "expected": 50, "observed": 75},
    )
    assert "max_slippage_bps violated" in _format_security_exception(exc)
