# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio

from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_ainvoke_guardian_run_delegate(monkeypatch) -> None:
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    monkeypatch.setattr(tool, "_invoke_guardian", lambda *a, **k: "ok")
    monkeypatch.setattr(tool, "_ainvoke_guardian", lambda *a, **k: asyncio.sleep(0, result="ok"))
    assert asyncio.run(tool._arun("payload")) == "ok"
