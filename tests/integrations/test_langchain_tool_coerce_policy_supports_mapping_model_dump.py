# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


class _DummyPolicy:
    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        return {"max_slippage_bps": 12, "forbidden_methods": ["0xa9059cbb"]}


class _DummyResult:
    def model_dump_json(self) -> str:
        return '{"ok": true}'


def test_test_langchain_tool_coerce_policy_supports_mapping_model_dump() -> None:
    assert LirixSecurityValidator._coerce_policy({"a": 1}) == {"a": 1}
    assert LirixSecurityValidator._coerce_policy(_DummyPolicy()) == {
        "max_slippage_bps": 12,
        "forbidden_methods": ["0xa9059cbb"],
    }


def test_test_langchain_tool_coerce_policy_supports_mapping_model_dump_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix import Lirix

    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        assert intent == "swap"
        assert payload["raw_intent_or_calldata"] == "swap 1 ETH"
        assert payload["assert_erc20_balance_increase"] == {"token": "0x1", "amount": 3}
        assert payload["extra_flag"] is True
        assert kwargs["security_policy"] == {"max_slippage_bps": 10}
        return _DummyResult()

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"],
        default_intent="swap",
        state_delta_assertions={"assert_erc20_balance_increase": {"token": "0x1", "amount": 3}},
        security_policy={"max_slippage_bps": 10},
    )
    assert tool._run("swap 1 ETH", extra_flag=True) == '{"ok": true}'


def test_test_langchain_tool_coerce_policy_supports_mapping_model_dump_3() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="blocked",
        context={"policy_key": "max_slippage_bps", "expected": 50, "observed": 500},
    )
    assert "max_slippage_bps violated" in _format_security_exception(exc)
