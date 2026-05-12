import json
from typing import Any, Optional

from lirix.core.constants import canonicalize_error_code


class LirixBaseException(Exception):
    """Base exception that adapts legacy v1.0.0 fields to the v1.1.2+ contract.

    This adapter ensures v1.0.0 legacy raises (e.g., hook_point, context) are
    safely translated into the v1.1.2+ JSON Standard Error Contract.
    """

    def __init__(
        self,
        error_code: str = "LRX_LEGACY_ERROR",
        resolution_agent: Optional[str] = None,
        resolution_dev: Optional[str] = None,
        value_protected: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("error_code", error_code)
        if resolution_agent is not None:
            kwargs.setdefault("resolution_agent", resolution_agent)
        if resolution_dev is not None:
            kwargs.setdefault("resolution_dev", resolution_dev)
        if value_protected is not None:
            kwargs.setdefault("value_protected", value_protected)
        if context is not None:
            kwargs.setdefault("context", context)
        adapter_state = self._adapt_legacy_kwargs(**kwargs)
        self.error_code = str(adapter_state["error_code"])
        # Governance-only canonicalization. Keep legacy error_code + context unchanged.
        self.canonical_error_code = canonicalize_error_code(self.error_code)
        self.value_protected = str(adapter_state["value_protected"])
        self.resolution_for_agent = str(adapter_state["resolution_for_agent"])
        self.resolution_for_developer = str(adapter_state["resolution_for_developer"])
        self.context = adapter_state["context"]
        self.human_readable_reason = self.resolution_for_agent
        self.hook_point = adapter_state["hook_point"]
        super().__init__(self.to_json())

    @classmethod
    def _adapt_legacy_kwargs(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Facade/Adapter layer: normalize legacy construction patterns into the
        # current JSON error contract without forcing callers to update at once.
        error_code = str(kwargs.get("error_code", "LRX_LEGACY_ERROR"))
        value_protected = str(kwargs.get("value_protected", "Unknown Asset Value"))
        legacy_reason = str(
            kwargs.get("human_readable_reason", "An internal validation error occurred.")
        )
        resolution_for_agent = str(kwargs.get("resolution_agent", legacy_reason))
        legacy_hook = str(kwargs.get("hook_point", "Check internal logs."))
        resolution_for_developer = str(kwargs.get("resolution_dev", legacy_hook))
        if args:
            resolution_for_agent = str(args[0])
        context = kwargs.get("context", {})
        if not isinstance(context, dict):
            context = {"raw_context": context}
        return {
            "error_code": error_code,
            "value_protected": value_protected,
            "resolution_for_agent": resolution_for_agent,
            "resolution_for_developer": resolution_for_developer,
            "context": context,
            "hook_point": kwargs.get("hook_point"),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "canonical_error_code": self.canonical_error_code,
            "resolution_for_agent": self.resolution_for_agent,
            "resolution_for_developer": self.resolution_for_developer,
            "value_protected": self.value_protected,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class LirixSimulationError(LirixBaseException):
    pass


class LirixHallucinationError(LirixBaseException):
    pass


class LirixCircuitBreakerError(LirixBaseException):
    pass


class CircuitBreakerOpenException(LirixCircuitBreakerError):
    """RPC / timeout circuit open; same lattice as LirixCircuitBreakerError for L4 parity."""

    pass


class LirixStateAssertionError(LirixBaseException):
    pass


class LirixRPCError(LirixBaseException):
    pass


class LirixSecurityException(LirixBaseException):
    pass


class InvalidIntentException(LirixSecurityException):
    pass


class LirixDependencyError(LirixBaseException):
    pass


class ConfigurationGuardException(LirixBaseException):
    pass


class HookExecutionException(LirixBaseException):
    pass


class RPCUnavailableException(LirixBaseException):
    pass


class ValidationFailedException(LirixBaseException):
    pass


class HookUnknownPointException(LirixBaseException):
    pass


class HookAsyncContextException(LirixBaseException):
    pass


class AddressChecksumException(LirixBaseException):
    pass


class SchemaValidationException(LirixBaseException):
    pass


class SimulationFailedException(LirixBaseException):
    pass


class MulticallEncodingException(LirixBaseException):
    pass


class MaliciousPayloadException(LirixBaseException):
    pass


class DeFiSlippageMissingException(LirixBaseException):
    pass


class RPCQuotaExhaustedException(LirixBaseException):
    pass


class InsufficientFeeException(LirixBaseException):
    pass


class NonceDesyncException(LirixBaseException):
    pass


class ContractPausedException(LirixBaseException):
    pass


class LirixPolicyViolationException(LirixBaseException):
    pass
