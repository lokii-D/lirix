# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix.integrations.autogen.tool import alirix_validate_intent, lirix_validate_intent
from lirix.integrations.langchain.tool import LirixSecurityValidator


class _HugeJsonModel:
    def model_dump_json(self) -> str:
        return "z" * 51201


def test_langchain_guardian_sync_feedback_on_oversized_model_dump_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, *a: Any, **k: Any) -> Any:
        return _HugeJsonModel()

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    out = tool._run('{"intent":"swap"}')
    assert "50KB" in out or "security bound" in out.lower()


@pytest.mark.asyncio
async def test_langchain_ainvoke_guardian_feedback_on_oversized_model_dump_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_async_validate_and_simulate(self: Any, *a: Any, **k: Any) -> Any:
        return _HugeJsonModel()

    monkeypatch.setattr(
        "lirix.Lirix.async_validate_and_simulate",
        fake_async_validate_and_simulate,
    )
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    out = await tool._ainvoke_guardian('{"intent":"swap"}')
    assert "50KB" in out or "security bound" in out.lower()


def test_autogen_lirix_validate_intent_feedback_on_oversized_model_dump_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, *a: Any, **k: Any) -> Any:
        return _HugeJsonModel()

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    out = lirix_validate_intent('{"x":1}', ["https://example.invalid"])
    assert "50KB" in out or "ACTION REQUIRED" in out


@pytest.mark.asyncio
async def test_autogen_alirix_validate_intent_feedback_on_oversized_model_dump_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, *a: Any, **k: Any) -> Any:
        return _HugeJsonModel()

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    out = await alirix_validate_intent('{"x":1}', ["https://example.invalid"])
    assert "50KB" in out or "ACTION REQUIRED" in out
