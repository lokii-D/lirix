from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from lirix.core.constants import (
    LIRIX_ERR_ADDRESS_CHECKSUM,
    LIRIX_ERR_CIRCUIT_BREAKER_OPEN,
    LIRIX_ERR_CONFIGURATION_GUARD,
    LIRIX_ERR_CONTRACT_PAUSED,
    LIRIX_ERR_DEFI_SLIPPAGE_MISSING,
    LIRIX_ERR_HOOK_ASYNC_REQUIRED,
    LIRIX_ERR_HOOK_EXECUTION,
    LIRIX_ERR_HOOK_UNKNOWN_POINT,
    LIRIX_ERR_INSUFFICIENT_FEE,
    LIRIX_ERR_INVALID_INTENT,
    LIRIX_ERR_MALICIOUS_PAYLOAD,
    LIRIX_ERR_MULTICALL_ENCODING,
    LIRIX_ERR_NONCE_DESYNC,
    LIRIX_ERR_RPC_QUOTA_EXHAUSTED,
    LIRIX_ERR_RPC_UNAVAILABLE,
    LIRIX_ERR_SCHEMA_VALIDATION,
    LIRIX_ERR_SIMULATION_FAILED,
    LIRIX_ERR_VALIDATION_FAILED,
    build_agent_resolution,
)


class LirixSecurityException(Exception):
    """Lirix 安全域统一异常基类（Error Empathy 五层结构，仅允许关键字实例化）。"""

    error_code: str
    human_readable_reason: str
    context: Dict[str, Any]
    resolution_for_agent: Dict[str, Any]
    resolution_for_developer: str

    def __init__(
        self,
        *,
        error_code: str,
        human_readable_reason: str,
        context: Mapping[str, Any],
        resolution_for_agent: Mapping[str, Any],
        resolution_for_developer: str,
    ) -> None:
        if not error_code.startswith("LIRIX_ERR_"):
            raise ValueError("error_code must start with LIRIX_ERR_")
        self.error_code = error_code
        self.human_readable_reason = human_readable_reason
        self.context = dict(context)
        self.resolution_for_agent = dict(resolution_for_agent)
        self.resolution_for_developer = resolution_for_developer
        super().__init__(human_readable_reason)

    def to_empathy_payload(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "human_readable_reason": self.human_readable_reason,
            "context": self.context,
            "resolution_for_agent": self.resolution_for_agent,
            "resolution_for_developer": self.resolution_for_developer,
        }


class CircuitBreakerOpenException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str = "Circuit breaker is open; execution blocked.",
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = "Inspect breaker policy and upstream failure reasons.",
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="halt_and_surface",
            notes="Stop automated retries; surface blocked state to operator.",
        )
        super().__init__(
            error_code=LIRIX_ERR_CIRCUIT_BREAKER_OPEN,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class InvalidIntentException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = "Validate intent schema and policy allow-lists.",
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="reject_intent",
            target_field="intent",
            notes="Reject the draft and request a corrected intent payload.",
        )
        super().__init__(
            error_code=LIRIX_ERR_INVALID_INTENT,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class ConfigurationGuardException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = "Fix LirixConfig fields and restart with validated config.",
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="fix_configuration",
            target_field="LirixConfig",
            notes="Halt pipeline; request configuration correction.",
        )
        super().__init__(
            error_code=LIRIX_ERR_CONFIGURATION_GUARD,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class HookExecutionException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = "Inspect hook implementation and exception chaining.",
    ) -> None:
        ctx = dict(context or {})
        hp = ctx.get("hook_point")
        if hp:
            agent = resolution_for_agent or build_agent_resolution(
                action="disable_or_rollback_hook",
                hook_point=str(hp),
                notes="Disable offending hook or rollback plugin version.",
            )
        else:
            agent = resolution_for_agent or build_agent_resolution(
                action="disable_or_rollback_hook",
                notes="Disable offending hook or rollback plugin version.",
            )
        super().__init__(
            error_code=LIRIX_ERR_HOOK_EXECUTION,
            human_readable_reason=human_readable_reason,
            context=ctx,
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class RPCUnavailableException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str = "RPC unavailable; fail-closed without cached chain state.",
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Restore RPC or adjust routing; never downgrade with cache."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="block_until_rpc_restored",
            retry=False,
            notes=(
                "Block execution; do not infer chain state from stale data. "
                "Fail-closed: no cached-block downgrade."
            ),
        )
        super().__init__(
            error_code=LIRIX_ERR_RPC_UNAVAILABLE,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class ValidationFailedException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = "Align validators with intended calldata constraints.",
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="reject_payload",
            notes="Reject payload and return validation diagnostics.",
        )
        super().__init__(
            error_code=LIRIX_ERR_VALIDATION_FAILED,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class HookUnknownPointException(LirixSecurityException):
    def __init__(
        self,
        *,
        hook_point: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        merged = dict(context or {})
        merged.setdefault("hook_point", hook_point)
        super().__init__(
            error_code=LIRIX_ERR_HOOK_UNKNOWN_POINT,
            human_readable_reason=f"Unknown hook point: {hook_point}",
            context=merged,
            resolution_for_agent=build_agent_resolution(
                action="use_predefined_hook_point",
                hook_point=hook_point,
                target_field="hook_point",
            ),
            resolution_for_developer="Register hooks against documented hook point names.",
        )


class HookAsyncContextException(LirixSecurityException):
    def __init__(
        self,
        *,
        hook_point: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        merged = dict(context or {})
        merged.setdefault("hook_point", hook_point)
        super().__init__(
            error_code=LIRIX_ERR_HOOK_ASYNC_REQUIRED,
            human_readable_reason="Async hooks registered; synchronous invoke is not supported.",
            context=merged,
            resolution_for_agent=build_agent_resolution(
                action="await_ainvoke_hooks",
                hook_point=hook_point,
                notes="Call ainvoke_hooks instead of invoke_hooks when async hooks exist.",
            ),
            resolution_for_developer=(
                "Call ainvoke_hooks instead of invoke_hooks when async hooks exist."
            ),
        )


class AddressChecksumException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        ctx = dict(context or {})
        super().__init__(
            error_code=LIRIX_ERR_ADDRESS_CHECKSUM,
            human_readable_reason=human_readable_reason,
            context=ctx,
            resolution_for_agent=build_agent_resolution(
                action="retry_with_checksum",
                target_field=str(ctx.get("field", "address")),
                notes="Normalize with Web3.to_checksum_address before constructing config.",
            ),
            resolution_for_developer=(
                "Normalize with Web3.to_checksum_address before constructing config."
            ),
        )


class SchemaValidationException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Align payload fields with SchemaValidator constraints (checksum, bounds)."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="reject_payload",
            target_field="payload",
            notes="Reject payload; fix schema violations before re-submitting.",
        )
        super().__init__(
            error_code=LIRIX_ERR_SCHEMA_VALIDATION,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class SimulationFailedException(LirixSecurityException):
    """L5：eth_call 模拟回滚（零 Gas）失败，携带可读的 EVM revert 语义。"""

    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Inspect revert reason, allowance, balance, and calldata against on-chain state."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="reject_or_fix_payload",
            notes=(
                "Simulation indicates the transaction would revert on-chain; "
                "do not sign or broadcast."
            ),
        )
        super().__init__(
            error_code=LIRIX_ERR_SIMULATION_FAILED,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class MulticallEncodingException(LirixSecurityException):
    """Multicall3 原子打包编码失败（不广播、不签名）。"""

    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Fix transaction dicts (to, data, value) and Multicall3 address; "
            "verify EIP-2930 access list requirements off-line."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="reject_or_fix_payload",
            notes="Multicall aggregate encoding failed; do not broadcast partial calldata.",
        )
        super().__init__(
            error_code=LIRIX_ERR_MULTICALL_ENCODING,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class MaliciousPayloadException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Inspect nested calldata, router targets, and allow-lists for route poisoning."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="halt_and_surface",
            notes=(
                "Block execution; nested calldata indicates malicious routing or recipient drift."
            ),
        )
        super().__init__(
            error_code=LIRIX_ERR_MALICIOUS_PAYLOAD,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class DeFiSlippageMissingException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Set a non-zero amountOutMin after computing slippage from price impact and tolerance."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="compute_and_set_slippage",
            notes="Never allow amountOutMin=0 for swap routes; derive a bounded minimum output.",
        )
        super().__init__(
            error_code=LIRIX_ERR_DEFI_SLIPPAGE_MISSING,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class RPCQuotaExhaustedException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Back off for an extended interval and switch to quota-aware RPC routing."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="sleep_and_retry_later",
            retry=True,
            notes=(
                "Received RPC 429 / quota exhaustion; stop retries and sleep for a long interval."
            ),
        )
        super().__init__(
            error_code=LIRIX_ERR_RPC_QUOTA_EXHAUSTED,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class InsufficientFeeException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Increase balance or reduce value/gas assumptions, including L2 data fee."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="increase_fee_budget",
            notes=(
                "Balance cannot cover value plus gas and data fee; reject or top up before "
                "broadcast."
            ),
        )
        super().__init__(
            error_code=LIRIX_ERR_INSUFFICIENT_FEE,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class NonceDesyncException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Refresh nonce state and serialize concurrent sends per account."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="refresh_nonce_and_retry",
            notes="Nonce conflicts detected; resync pending nonce state and serialize writes.",
        )
        super().__init__(
            error_code=LIRIX_ERR_NONCE_DESYNC,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )


class ContractPausedException(LirixSecurityException):
    def __init__(
        self,
        *,
        human_readable_reason: str,
        context: Optional[Mapping[str, Any]] = None,
        resolution_for_agent: Optional[Mapping[str, Any]] = None,
        resolution_for_developer: str = (
            "Stop interaction until contract is unpaused or route to an alternative venue."
        ),
    ) -> None:
        agent = resolution_for_agent or build_agent_resolution(
            action="halt_until_contract_resumes",
            retry=False,
            notes="Target contract is paused or blacklisted; do not broadcast.",
        )
        super().__init__(
            error_code=LIRIX_ERR_CONTRACT_PAUSED,
            human_readable_reason=human_readable_reason,
            context=dict(context or {}),
            resolution_for_agent=agent,
            resolution_for_developer=resolution_for_developer,
        )
