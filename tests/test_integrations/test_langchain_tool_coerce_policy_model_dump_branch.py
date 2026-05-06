# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_test_langchain_tool_coerce_policy_model_dump_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, int]:
            return {"x": 1}

    tool = LirixSecurityValidator(rpc_urls=["https://example.invalid"])
    assert tool._coerce_policy(_Model()) == {"x": 1}
