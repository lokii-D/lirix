# SPDX-License-Identifier: MIT
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Type, cast

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

import lirix as lirix_pkg
from lirix.core.exceptions import (
    LirixBaseException,
    LirixPolicyViolationException,
)

if TYPE_CHECKING:

    class BaseTool:
        name: str
        description: str

        def __init__(self, **kwargs: Any) -> None: ...

else:
    try:
        from langchain_core.tools import BaseTool
    except ImportError:

        class BaseTool:
            name = "BaseTool"
            description = "Optional fallback BaseTool stub."

            def __init__(self, **kwargs: Any) -> None:
                for key, value in kwargs.items():
                    setattr(self, key, value)


def _format_security_exception(exc: LirixBaseException) -> str:
    if (
        isinstance(exc, LirixPolicyViolationException)
        and getattr(exc, "error_code", None) == "LRX_SHADOW_POLICY_BLOCKED"
    ):
        context = exc.context if isinstance(exc.context, dict) else {}
        policy_key = context.get("policy_key", "unknown_policy")
        expected = context.get("expected")
        observed = context.get("observed")
        return (
            "Transaction Blocked by Lirix Policy: "
            f"{policy_key} violated (expected={expected}, observed={observed}). "
            f"{exc.resolution_for_agent}"
        )
    return str(exc.resolution_for_agent)


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
        "Official LangChain tool for Lirix's Triple-Zero Standard. You MUST use "
        "this tool before executing any on-chain swap, transfer, multicall, or "
        "contract call. Pass the raw intent/calldata verbatim. The tool will "
        "validate the payload, simulate execution, and return either a safe "
        "result or a remediation string that lets the agent self-correct."
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
        **kwargs: Any,
    ) -> None:
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
        **kwargs: Any,
    ) -> str:
        guardian = lirix_pkg.Lirix(rpc_urls=self._rpc_urls)
        resolved_intent = intent or self._default_intent or "unknown"
        merged_assertions = dict(self._state_delta_assertions)
        if state_delta_assertions is not None:
            merged_assertions.update(dict(state_delta_assertions))
        merged_security_policy = dict(self._security_policy)
        if security_policy is not None:
            merged_security_policy.update(self._coerce_policy(security_policy))
        try:
            result = guardian.validate_and_simulate(
                resolved_intent,
                {"raw_intent_or_calldata": raw_intent_or_calldata, **merged_assertions, **kwargs},
                security_policy=merged_security_policy or None,
            )
        except LirixBaseException as exc:
            return _format_security_exception(exc)
        if hasattr(result, "model_dump_json"):
            return str(cast(Any, result).model_dump_json())
        return str(result)

    async def _ainvoke_guardian(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        guardian = lirix_pkg.Lirix(rpc_urls=self._rpc_urls)
        resolved_intent = intent or self._default_intent or "unknown"
        merged_assertions = dict(self._state_delta_assertions)
        if state_delta_assertions is not None:
            merged_assertions.update(dict(state_delta_assertions))
        merged_security_policy = dict(self._security_policy)
        if security_policy is not None:
            merged_security_policy.update(self._coerce_policy(security_policy))
        try:
            result = await guardian.async_validate_and_simulate(
                resolved_intent,
                {"raw_intent_or_calldata": raw_intent_or_calldata, **merged_assertions, **kwargs},
                security_policy=merged_security_policy or None,
            )
        except LirixBaseException as exc:
            return _format_security_exception(exc)
        if hasattr(result, "model_dump_json"):
            return str(cast(Any, result).model_dump_json())
        return str(result)

    def _run(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        return self._invoke_guardian(
            raw_intent_or_calldata,
            intent=intent,
            state_delta_assertions=state_delta_assertions,
            security_policy=security_policy,
            **kwargs,
        )

    async def _arun(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        result = await asyncio.to_thread(
            self._invoke_guardian,
            raw_intent_or_calldata,
            intent,
            state_delta_assertions,
            security_policy,
            **kwargs,
        )
        return result
