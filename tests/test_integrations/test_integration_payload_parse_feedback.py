# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Integration boundary: invalid brace-JSON must return agent-facing strings, not bare exceptions."""

from __future__ import annotations

from lirix.integrations.autogen.tool import lirix_validate_intent
from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_langchain_tool_invalid_brace_json_returns_action_required() -> None:
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    out = tool._run("{not valid json}")
    assert out.startswith("ACTION REQUIRED:")
    assert "Failed to parse payload" in out


def test_autogen_lirix_validate_intent_invalid_brace_json_returns_action_required() -> None:
    out = lirix_validate_intent("{bad}", rpc_urls=["https://example.invalid"])
    assert out.startswith("ACTION REQUIRED:")
    assert "Failed to parse payload" in out
