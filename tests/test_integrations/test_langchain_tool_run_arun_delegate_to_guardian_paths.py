# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_run_arun_delegate_to_guardian_paths(monkeypatch) -> None:
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"], default_intent="swap")
    monkeypatch.setattr(tool, "_invoke_guardian", lambda *a, **k: "ok")
    assert tool._run("payload") == "ok"
