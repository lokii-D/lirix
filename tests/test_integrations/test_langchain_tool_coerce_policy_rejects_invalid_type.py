# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_coerce_policy_rejects_invalid_type() -> None:
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    try:
        tool._coerce_policy(123)
    except TypeError as exc:
        assert "mapping or Pydantic model" in str(exc)
    else:
        raise AssertionError("expected TypeError")
