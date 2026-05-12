# SPDX-License-Identifier: MIT
"""LangChain tool integration.

Requires optional dependency ``langchain_core`` for full functionality.
When ``langchain_core`` is absent, a minimal ``BaseTool`` stub exists only for
isolated tests. Production integrations should install ``langchain-core`` and pass
``optional_deps_mode="fail_closed"`` so missing optional deps fail closed
instead of using the stub.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Literal, Mapping, Optional, Sequence, Type, cast

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from lirix import Lirix
from lirix.core.exceptions import (
    ConfigurationGuardException,
    LirixBaseException,
    LirixPolicyViolationException,
)

_LANGCHAIN_CORE_AVAILABLE: bool = False

if TYPE_CHECKING:

    class BaseTool:
        name: str
        description: str

        def __init__(self, **kwargs: Any) -> None: ...

else:
    try:  # pragma: no cover
        from langchain_core.tools import BaseTool  # pragma: no cover

        _LANGCHAIN_CORE_AVAILABLE = True
    except ImportError:  # pragma: no cover

        class BaseTool:  # pragma: no cover - exercised only when langchain_core absent
            name = "BaseTool"
            description = "Optional fallback BaseTool stub."

            def __init__(self, **kwargs: Any) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)


def _format_payload_parse_feedback(exc: ValueError) -> str:
    """Remediation when JSON-shaped intent text fails to parse (integrations boundary)."""

    return f"ACTION REQUIRED: {exc}"


def _merge_raw_intent_overlay(
    *,
    raw_intent_or_calldata: str,
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten JSON-shaped agent strings into the pipeline draft (integrations-only helper).

    Explicit ``overlay`` keys (state deltas, kwargs) win over parsed JSON fields so callers
    can tighten assertions without the model overriding them.
    """

    parsed: dict[str, Any] = {}
    raw_txt = raw_intent_or_calldata.strip()
    if raw_txt.startswith("{") and raw_txt.endswith("}"):
        try:
            blob = json.loads(raw_txt)
        except json.JSONDecodeError as exc:
            raise ValueError("Failed to parse payload. You MUST output valid JSON.") from exc
        if isinstance(blob, dict):
            parsed.update(blob)
    return {**parsed, "raw_intent_or_calldata": raw_intent_or_calldata, **dict(overlay)}


def _format_security_exception(exc: LirixBaseException) -> str:
    context = exc.context if isinstance(exc.context, dict) else {}
    protocol = context.get("failure_protocol")
    resolved_feedback: Mapping[str, Any] = {}
    if isinstance(protocol, Mapping):
        resolved_feedback = Lirix.resolve_failure_protocol({"failure_protocol": protocol})
    canonical_error = str(getattr(exc, "canonical_error_code", "") or "")
    if (
        isinstance(exc, LirixPolicyViolationException)
        and canonical_error == "LIRIX_ERR_POLICY_BLOCKED"
    ):
        policy_key = context.get("policy_key", "unknown_policy")
        expected = context.get("expected")
        observed = context.get("observed")
        return (
            "Transaction Blocked by Lirix Policy: "
            f"{policy_key} violated (expected={expected}, observed={observed}). "
            f"{exc.resolution_for_agent}"
        )
    remediation = resolved_feedback.get("remediation")
    base = remediation.strip() if isinstance(remediation, str) and remediation.strip() else str(
        exc.resolution_for_agent
    )
    hr = str(getattr(exc, "human_readable_reason", "") or "").strip()
    lines = [base]
    if hr and hr.lower() != base.lower():
        lines.append(f"Reject detail: {hr}")
    rc = str(resolved_feedback.get("reason_code") or "").strip()
    if rc:
        lines.append(f"Reason code: {rc}")
    repair = ""
    if isinstance(protocol, Mapping):
        rh = protocol.get("repair_hint")
        if isinstance(rh, str) and rh.strip():
            repair = rh.strip()
    if repair and repair.lower() not in base.lower():
        lines.append(f"Next step: {repair}")
    return "\n".join(lines)


def _serialize_guardian_success(result: Any) -> str:
    """Serialize a Lirix success envelope as JSON with additive ``tx_payload``.

    ``tx_payload`` is injected only when the value is serialized from a ``Mapping``,
    from ``model_dump`` (mapping branch), or from ``model_dump_json`` after a JSON
    parse into a ``dict``. If the result is neither a mapping nor a Pydantic model
    handled above, the final fallback is ``str(result)`` **without** ``tx_payload``
    so plain-string tool outputs stay unchanged for downstream parsers.

    This non-JSON fallback intentionally carries no ``tx_payload`` so callers can
    distinguish plain textual outputs from structured broadcast-ready envelopes.
    """
    if hasattr(result, "model_dump"):
        dumped = cast(Any, result).model_dump(mode="python")
        if not isinstance(dumped, Mapping):
            return json.dumps(dumped, sort_keys=True, default=str)
        out = dict(dumped)
        out["tx_payload"] = Lirix.extract_broadcast_fields(out)
        return json.dumps(out, sort_keys=True, default=str)
    if isinstance(result, Mapping):
        out = dict(result)
        out["tx_payload"] = Lirix.extract_broadcast_fields(result)
        return json.dumps(out, sort_keys=True, default=str)
    if hasattr(result, "model_dump_json"):
        raw = str(cast(Any, result).model_dump_json())
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if not isinstance(parsed, dict):
            return raw
        out = dict(parsed)
        out["tx_payload"] = Lirix.extract_broadcast_fields(out)
        return json.dumps(out, sort_keys=True, default=str)
    return str(result)


class LirixSecurityValidatorInput(BaseModel):
    """Input contract for `LirixSecurityValidator`.

    raw_intent_or_calldata must contain the untrusted agent output, calldata,
    or swap/transfer/contract-call intent verbatim.

    state_delta_assertions may carry L5-style expectations such as
    `assert_erc20_balance_increase` so the agent can provide a fallback proof
    target when the intent requires post-simulation reasoning.
    """

    raw_intent_or_calldata: str = Field(
        ...,
        description=(
            "Raw intent, calldata, or model output to validate before any on-chain execution."
        ),
    )
    intent: Optional[str] = Field(
        default=None,
        description="Optional execution intent label such as swap, transfer, or contract_call.",
    )
    state_delta_assertions: Optional[Mapping[str, Any]] = Field(
        default=None,
        description=(
            "Optional assertion map for L5 state-delta expectations, such as "
            "assert_erc20_balance_increase."
        ),
    )
    security_policy: Optional[Mapping[str, Any]] = Field(
        default=None,
        description=(
            "Optional human-defined hard policy. When present, Lirix overrides weak model "
            "assertions and blocks policy violations."
        ),
    )
    mode: Optional[str] = Field(
        default=None,
        description=(
            "Optional execution mode: validate_only or validate_and_simulate. "
            "Defaults to validate_and_simulate for backward compatibility."
        ),
    )


class LirixSecurityValidator(BaseTool):
    """LangChain-native security boundary for Web3 agents.

    LirixSecurityValidator is the official LangChain wrapper around Lirix's
    Triple-Zero Standard: zero private-key exposure, zero telemetry leakage,
    and zero-trust execution of untrusted agent output. Use it as the first
    tool in any chain-aware agent whenever the model might emit a swap,
    transfer, multicall, or contract invocation.

    The tool accepts raw intent or calldata, validates it through Lirix, and
    returns either a mathematically verified execution result or a remediation
    string via `LirixSecurityException.resolution_for_agent`.

    Example:

    ```python
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_openai import ChatOpenAI
    from lirix.integrations.langchain import LirixSecurityValidator

    validator = LirixSecurityValidator(
        rpc_urls=["https://eth-mainnet.example"],
        default_intent="swap",
        state_delta_assertions={
            "assert_erc20_balance_increase": {"token": "0xToken", "amount": 25}
        },
    )

    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_tool_calling_agent(llm, tools=[validator])
    executor = AgentExecutor(agent=agent, tools=[validator])
    result = executor.invoke({"input": "swap 1 ETH for USDC on Uniswap"})
    ```
    """

    name: str = "LirixSecurityValidator"
    description: str = (
        "Official LangChain tool for Lirix's Triple-Zero Standard. You MUST invoke "
        "this tool before broadcasting any on-chain swap, transfer, multicall, or "
        "contract call — skipping it is a critical safety violation. Pass model "
        "output / calldata verbatim (JSON swap intents are flattened automatically). "
        "Returns either an approved simulation envelope (JSON with additive tx_payload) "
        "or a remediation string with rejection reasons and fix guidance."
    )
    args_schema: Type[BaseModel] = LirixSecurityValidatorInput
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _rpc_urls: list[str] = PrivateAttr(default_factory=list)
    _default_intent: Optional[str] = PrivateAttr(default=None)
    _state_delta_assertions: dict[str, Any] = PrivateAttr(default_factory=dict)
    _security_policy: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init__(
        self,
        *,
        rpc_urls: Sequence[str],
        default_intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        policy: Optional[Any] = None,
        optional_deps_mode: Literal["best_effort", "fail_closed"] = "best_effort",
        **kwargs: Any,
    ) -> None:
        if optional_deps_mode == "fail_closed" and not _LANGCHAIN_CORE_AVAILABLE:
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "optional_deps_mode=fail_closed requires langchain_core to be installed."
                ),
                context={"reason": "missing_optional_dependency", "dependency": "langchain_core"},
            )
        super().__init__(**kwargs)
        self._rpc_urls = list(rpc_urls)
        self._default_intent = default_intent
        self._state_delta_assertions = dict(state_delta_assertions or {})
        self._security_policy = self._coerce_policy(security_policy)
        if policy is not None:
            self._security_policy.update(self._coerce_policy(policy))

    @staticmethod
    def _coerce_policy(policy: Optional[Any]) -> dict[str, Any]:
        if policy is None:
            return {}
        if isinstance(policy, Mapping):
            return dict(policy)
        if hasattr(policy, "model_dump"):
            return dict(cast(Any, policy).model_dump(mode="python"))
        raise TypeError("policy must be a mapping or Pydantic model.")

    def _invoke_guardian(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        resolved_intent = intent or self._default_intent or "unknown"
        merged_assertions = dict(self._state_delta_assertions)
        if state_delta_assertions is not None:
            merged_assertions.update(dict(state_delta_assertions))
        merged_security_policy = dict(self._security_policy)
        if security_policy is not None:
            merged_security_policy.update(self._coerce_policy(security_policy))
        try:
            payload = _merge_raw_intent_overlay(
                raw_intent_or_calldata=raw_intent_or_calldata,
                overlay={**merged_assertions, **kwargs},
            )
        except ValueError as exc:
            return _format_payload_parse_feedback(exc)
        guardian = Lirix(rpc_urls=self._rpc_urls)
        try:
            token = str(mode or "validate_and_simulate").strip().lower()
            if token == "validate_only":
                result = guardian.validate_only(resolved_intent, payload)
            else:
                result = guardian.validate_and_simulate(
                    resolved_intent,
                    payload,
                    security_policy=merged_security_policy or None,
                )
        except LirixBaseException as exc:
            return _format_security_exception(exc)
        return _serialize_guardian_success(result)

    async def _ainvoke_guardian(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        resolved_intent = intent or self._default_intent or "unknown"
        merged_assertions = dict(self._state_delta_assertions)
        if state_delta_assertions is not None:
            merged_assertions.update(dict(state_delta_assertions))
        merged_security_policy = dict(self._security_policy)
        if security_policy is not None:
            merged_security_policy.update(self._coerce_policy(security_policy))
        try:
            payload = _merge_raw_intent_overlay(
                raw_intent_or_calldata=raw_intent_or_calldata,
                overlay={**merged_assertions, **kwargs},
            )
        except ValueError as exc:
            return _format_payload_parse_feedback(exc)
        guardian = Lirix(rpc_urls=self._rpc_urls)
        try:
            token = str(mode or "validate_and_simulate").strip().lower()
            if token == "validate_only":
                result = await guardian.async_validate_only(resolved_intent, payload)
            else:
                result = await guardian.async_validate_and_simulate(
                    resolved_intent,
                    payload,
                    security_policy=merged_security_policy or None,
                )
        except LirixBaseException as exc:
            return _format_security_exception(exc)
        return _serialize_guardian_success(result)

    def _run(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        return self._invoke_guardian(
            raw_intent_or_calldata,
            intent=intent,
            state_delta_assertions=state_delta_assertions,
            security_policy=security_policy,
            mode=mode,
            **kwargs,
        )

    async def _arun(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        result = await asyncio.to_thread(
            self._invoke_guardian,
            raw_intent_or_calldata,
            intent,
            state_delta_assertions,
            security_policy,
            mode,
            **kwargs,
        )
        return result
