from __future__ import annotations

from typing import Any

import pytest
from lirix.core.exceptions import LirixSecurityException
from lirix.integrations.langchain.tool import BaseTool, LirixSecurityValidator


def test_test_langchain_tool_fallback_basetool_sets_attributes_from_kwargs() -> None:
    tool = BaseTool(alpha=1, beta="x")
    assert tool.alpha == 1
    assert tool.beta == "x"


@pytest.mark.asyncio
async def test_ainvoke_guardian_success_uses_async_lirix(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_async_validate_and_simulate(
        self: Any, intent: str, payload: dict[str, Any], **kwargs: Any
    ) -> Any:
        captured["intent"] = intent
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return {"ok": True, "path": "async"}

    monkeypatch.setattr("lirix.Lirix.async_validate_and_simulate", fake_async_validate_and_simulate)

    validator = LirixSecurityValidator(
        rpc_urls=["https://example.invalid"],
        default_intent="transfer",
        state_delta_assertions={"min_delta": 1},
        security_policy={"strict": True},
    )

    result = await validator._ainvoke_guardian(
        "payload",
        state_delta_assertions={"max_delta": 2},
        security_policy={"allow_revert": False},
        trace_id="t-1",
    )

    assert result == "{'ok': True, 'path': 'async'}"
    assert captured["intent"] == "transfer"
    assert captured["payload"]["raw_intent_or_calldata"] == "payload"
    assert captured["payload"]["min_delta"] == 1
    assert captured["payload"]["max_delta"] == 2
    assert captured["payload"]["trace_id"] == "t-1"
    assert captured["kwargs"]["security_policy"] == {"strict": True, "allow_revert": False}


@pytest.mark.asyncio
async def test_ainvoke_guardian_returns_remediation_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_async_validate_and_simulate(
        self: Any, intent: str, payload: dict[str, Any], **kwargs: Any
    ) -> Any:
        raise LirixSecurityException(
            resolution_agent="Async simulation blocked. Use safer calldata and retry."
        )

    monkeypatch.setattr("lirix.Lirix.async_validate_and_simulate", fake_async_validate_and_simulate)
    validator = LirixSecurityValidator(rpc_urls=["https://example.invalid"])

    result = await validator._ainvoke_guardian("unsafe")
    assert result == "Async simulation blocked. Use safer calldata and retry."
