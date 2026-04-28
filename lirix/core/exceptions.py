import json
from typing import Any, Optional


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
        self.error_code = adapter_state["error_code"]
        self.value_protected = adapter_state["value_protected"]
        self.resolution_for_agent = adapter_state["resolution_for_agent"]
        self.resolution_for_developer = adapter_state["resolution_for_developer"]
        self.context = adapter_state["context"]
        self.human_readable_reason = self.resolution_for_agent
        self.hook_point = adapter_state["hook_point"]
        super().__init__(self.to_json())

    @classmethod
    def _adapt_legacy_kwargs(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        # Facade/Adapter layer: normalize legacy construction patterns into the
        # current JSON error contract without forcing callers to update at once.
        error_code = kwargs.get("error_code", "LRX_LEGACY_ERROR")
        value_protected = kwargs.get("value_protected", "Unknown Asset Value")
        legacy_reason = kwargs.get(
            "human_readable_reason", "An internal validation error occurred."
        )
        resolution_for_agent = kwargs.get("resolution_agent", legacy_reason)
        legacy_hook = kwargs.get("hook_point", "Check internal logs.")
        resolution_for_developer = kwargs.get("resolution_dev", str(legacy_hook))
        if args:
            resolution_for_agent = str(args[0])
        return {
            "error_code": error_code,
            "value_protected": value_protected,
            "resolution_for_agent": resolution_for_agent,
            "resolution_for_developer": resolution_for_developer,
            "context": kwargs.get("context", {}),
            "hook_point": kwargs.get("hook_point"),
        }

    def to_dict(self) -> dict[str, str]:
        return {
            "error_code": self.error_code,
            "resolution_for_agent": self.resolution_for_agent,
            "resolution_for_developer": self.resolution_for_developer,
            "value_protected": self.value_protected,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class LirixSimulationError(LirixBaseException):
    pass


class LirixHallucinationError(LirixBaseException):
    pass


class LirixCircuitBreakerError(LirixBaseException):
    pass


class LirixStateAssertionError(LirixBaseException):
    pass


class LirixRPCError(LirixBaseException):
    pass


# Backward-compatible aliases for imports across the codebase.
class LirixSecurityException(LirixBaseException):
    pass


LirixDependencyError = LirixBaseException
CircuitBreakerOpenException = LirixBaseException
InvalidIntentException = LirixSecurityException
ConfigurationGuardException = LirixBaseException
HookExecutionException = LirixBaseException
RPCUnavailableException = LirixBaseException
ValidationFailedException = LirixBaseException
HookUnknownPointException = LirixBaseException
HookAsyncContextException = LirixBaseException
AddressChecksumException = LirixBaseException
SchemaValidationException = LirixBaseException
SimulationFailedException = LirixBaseException
MulticallEncodingException = LirixBaseException
MaliciousPayloadException = LirixBaseException
DeFiSlippageMissingException = LirixBaseException
RPCQuotaExhaustedException = LirixBaseException
InsufficientFeeException = LirixBaseException
NonceDesyncException = LirixBaseException
ContractPausedException = LirixBaseException
LirixPolicyViolationException = LirixBaseException
