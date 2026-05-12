# SPDX-License-Identifier: MIT
from __future__ import annotations

import lirix.integrations.langchain.tool as tool_mod
import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.integrations.langchain.tool import LirixSecurityValidator


def test_lirix_security_validator_fail_closed_raises_when_langchain_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool_mod, "_LANGCHAIN_CORE_AVAILABLE", False)
    with pytest.raises(ConfigurationGuardException) as ei:
        LirixSecurityValidator(
            rpc_urls=["https://example.invalid"], optional_deps_mode="fail_closed"
        )
    assert ei.value.context.get("dependency") == "langchain_core"
