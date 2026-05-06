# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix
from lirix.core.exceptions import LirixPolicyViolationException
from lirix.integrations.langchain.tool import LirixSecurityValidator, _format_security_exception


class _PolicyExc(LirixPolicyViolationException):
    pass


def test_test_langchain_tool_format_security_exception_includes_policy_details() -> None:
    exc = LirixPolicyViolationException(
        error_code="LRX_SHADOW_POLICY_BLOCKED",
        resolution_agent="blocked",
        resolution_dev="dev",
        value_protected="v",
        context={"policy_key": "forbidden_methods", "expected": ["a"], "observed": "b"},
    )
    text = _format_security_exception(exc)
    assert "forbidden_methods" in text
    assert "expected=['a']" in text
    assert "observed=b" in text


def test_test_langchain_tool_format_security_exception_includes_policy_details_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise LirixPolicyViolationException(
            error_code="LRX_SHADOW_POLICY_BLOCKED",
            resolution_agent="blocked",
            resolution_dev="dev",
            value_protected="v",
            context={"policy_key": "forbidden_methods", "expected": ["x"], "observed": "y"},
        )

    monkeypatch.setattr(Lirix, "validate_and_simulate", boom)
    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    assert tool._run("raw") == (
        "Transaction Blocked by Lirix Policy: forbidden_methods violated "
        "(expected=['x'], observed=y). blocked"
    )
