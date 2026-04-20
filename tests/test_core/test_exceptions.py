# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Dict, Type

import pytest
from lirix.core.constants import (
    RESOLUTION_FOR_AGENT_JSON_SCHEMA,
    build_agent_resolution,
)
from lirix.core.exceptions import (
    AddressChecksumException,
    CircuitBreakerOpenException,
    ConfigurationGuardException,
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    InsufficientFeeException,
    InvalidIntentException,
    LirixSecurityException,
    MaliciousPayloadException,
    MulticallEncodingException,
    NonceDesyncException,
    RPCUnavailableException,
    SchemaValidationException,
    SimulationFailedException,
    ValidationFailedException,
)


def test_lirix_security_exception_payload() -> None:
    exc = LirixSecurityException(
        error_code="LIRIX_ERR_TEST",
        human_readable_reason="reason",
        context={"k": 1},
        resolution_for_agent=build_agent_resolution(action="noop"),
        resolution_for_developer="d",
    )
    assert exc.to_empathy_payload()["error_code"] == "LIRIX_ERR_TEST"
    assert isinstance(exc.to_empathy_payload()["resolution_for_agent"], dict)


def test_lirix_security_exception_empty_context() -> None:
    exc = LirixSecurityException(
        error_code="LIRIX_ERR_TEST",
        human_readable_reason="reason",
        context={},
        resolution_for_agent=build_agent_resolution(action="noop"),
        resolution_for_developer="d",
    )
    assert exc.context == {}


def test_lirix_security_exception_rejects_positional_args() -> None:
    with pytest.raises(TypeError):
        LirixSecurityException(
            error_code="LIRIX_ERR_TEST",
            human_readable_reason="only positional",
            context={},
            resolution_for_agent=build_agent_resolution(action="noop"),
            resolution_for_developer="d",
        )


def test_lirix_security_exception_rejects_bad_error_code_prefix() -> None:
    with pytest.raises(ValueError, match="LIRIX_ERR_"):
        LirixSecurityException(
            error_code="ERR_BAD",
            human_readable_reason="x",
            context={},
            resolution_for_agent=build_agent_resolution(action="noop"),
            resolution_for_developer="d",
        )


def test_lirix_security_exception_requires_context_kwarg() -> None:
    with pytest.raises(TypeError):
        LirixSecurityException(
            error_code="LIRIX_ERR_TEST",
            human_readable_reason="x",
            context={},
            resolution_for_agent=build_agent_resolution(action="noop"),
            resolution_for_developer="d",
        )


def test_resolution_schema_is_dict() -> None:
    assert RESOLUTION_FOR_AGENT_JSON_SCHEMA["title"] == "LirixAgentResolution"


def test_build_agent_resolution_optional_fields() -> None:
    base = build_agent_resolution(action="a")
    assert base["schema_version"] == 1
    full = build_agent_resolution(
        action="b",
        target_field="to",
        retry=True,
        hook_point="pre_validate",
        notes="n",
        extra_key=1,
    )
    assert full["target_field"] == "to"
    assert full["extra_key"] == 1


@pytest.mark.parametrize(  # type: ignore[misc]
    "cls,kwargs",
    [
        (CircuitBreakerOpenException, {}),
        (
            InvalidIntentException,
            {"human_readable_reason": "bad intent"},
        ),
        (
            ConfigurationGuardException,
            {"human_readable_reason": "bad cfg"},
        ),
        (
            HookExecutionException,
            {"human_readable_reason": "hook failed"},
        ),
        (RPCUnavailableException, {}),
        (
            ValidationFailedException,
            {"human_readable_reason": "validation"},
        ),
        (
            AddressChecksumException,
            {"human_readable_reason": "checksum"},
        ),
        (
            SchemaValidationException,
            {"human_readable_reason": "schema"},
        ),
        (
            MaliciousPayloadException,
            {"human_readable_reason": "malicious"},
        ),
        (
            SimulationFailedException,
            {"human_readable_reason": "sim failed"},
        ),
        (
            MulticallEncodingException,
            {"human_readable_reason": "multicall encode"},
        ),
        (
            InsufficientFeeException,
            {"human_readable_reason": "insufficient fee"},
        ),
        (
            NonceDesyncException,
            {"human_readable_reason": "nonce desync"},
        ),
    ],
)
def test_predefined_exceptions_are_lirix(
    cls: Type[LirixSecurityException],
    kwargs: Dict[str, Any],
) -> None:
    exc = cls(**kwargs)
    assert isinstance(exc, LirixSecurityException)
    assert exc.error_code.startswith("LIRIX_ERR_")
    assert isinstance(exc.resolution_for_agent, dict)
    assert exc.resolution_for_agent.get("action")


def test_hook_unknown_point_exception_context_merge() -> None:
    exc = HookUnknownPointException(hook_point="x", context={"a": 1})
    assert exc.context["hook_point"] == "x"
    assert exc.context["a"] == 1


def test_hook_async_context_exception() -> None:
    exc = HookAsyncContextException(hook_point="pre_validate", context=None)
    assert exc.context["hook_point"] == "pre_validate"
