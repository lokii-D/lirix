# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.exceptions import LirixBaseException, LirixCircuitBreakerError, LirixRPCError


def test_test_exceptions_exception_adapter_defaults_subclasses() -> None:
    exc = LirixBaseException()
    assert exc.error_code == "LRX_LEGACY_ERROR"
    assert exc.to_dict()["value_protected"] == "Unknown Asset Value"
    assert isinstance(LirixCircuitBreakerError(error_code="x"), LirixBaseException)
    assert isinstance(LirixRPCError(error_code="x"), LirixBaseException)


def test_test_exceptions_exception_adapter_defaults_subclasses_2() -> None:
    adapted = LirixBaseException._adapt_legacy_kwargs(  # noqa: SLF001
        "agent reason from args",
        error_code="LRX_CUSTOM",
    )
    assert adapted["resolution_for_agent"] == "agent reason from args"
