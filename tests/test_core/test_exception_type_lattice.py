# SPDX-License-Identifier: MIT
from __future__ import annotations

import pytest
from lirix.core.exceptions import (
    AddressChecksumException,
    CircuitBreakerOpenException,
    ConfigurationGuardException,
    ContractPausedException,
    DeFiSlippageMissingException,
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    InsufficientFeeException,
    InvalidIntentException,
    LirixBaseException,
    LirixCircuitBreakerError,
    LirixDependencyError,
    LirixPolicyViolationException,
    LirixRPCError,
    LirixSecurityException,
    LirixSimulationError,
    MaliciousPayloadException,
    MulticallEncodingException,
    NonceDesyncException,
    RPCQuotaExhaustedException,
    RPCUnavailableException,
    SchemaValidationException,
    SimulationFailedException,
    ValidationFailedException,
)

_PUBLIC_EXCEPTION_TYPES = (
    AddressChecksumException,
    CircuitBreakerOpenException,
    ConfigurationGuardException,
    ContractPausedException,
    DeFiSlippageMissingException,
    HookAsyncContextException,
    HookExecutionException,
    HookUnknownPointException,
    InsufficientFeeException,
    InvalidIntentException,
    LirixCircuitBreakerError,
    LirixDependencyError,
    LirixPolicyViolationException,
    LirixRPCError,
    LirixSecurityException,
    LirixSimulationError,
    MaliciousPayloadException,
    MulticallEncodingException,
    NonceDesyncException,
    RPCQuotaExhaustedException,
    RPCUnavailableException,
    SchemaValidationException,
    SimulationFailedException,
    ValidationFailedException,
)


@pytest.mark.parametrize("exc_type", _PUBLIC_EXCEPTION_TYPES)
def test_public_exception_is_proper_subclass_not_base_alias(
    exc_type: type[LirixBaseException],
) -> None:
    assert issubclass(exc_type, LirixBaseException)
    assert exc_type is not LirixBaseException


def test_circuit_breaker_open_is_circuit_breaker_subclass() -> None:
    assert issubclass(CircuitBreakerOpenException, LirixCircuitBreakerError)
    assert CircuitBreakerOpenException is not LirixCircuitBreakerError


def test_invalid_intent_is_security_subclass_distinct() -> None:
    assert issubclass(InvalidIntentException, LirixSecurityException)
    assert InvalidIntentException is not LirixSecurityException


def test_raises_policy_violation_not_other_lirix_types() -> None:
    with pytest.raises(LirixPolicyViolationException):
        raise LirixPolicyViolationException(error_code="LRX_SHADOW_POLICY_BLOCKED")

    # Cross-type isinstance checks: see test_isinstance_policy_vs_config


def test_isinstance_policy_vs_config() -> None:
    p = LirixPolicyViolationException(error_code="p")
    c = ConfigurationGuardException(error_code="c")
    assert isinstance(p, LirixPolicyViolationException)
    assert not isinstance(c, LirixPolicyViolationException)
    assert isinstance(c, ConfigurationGuardException)
    assert not isinstance(p, ConfigurationGuardException)


def test_l4_circuit_open_caught_as_lirix_circuit_breaker_error() -> None:
    exc = CircuitBreakerOpenException(error_code="LRX_CB")
    assert isinstance(exc, LirixCircuitBreakerError)
