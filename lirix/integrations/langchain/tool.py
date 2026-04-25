# SPDX-License-Identifier: MIT
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Mapping, Optional, Sequence, Type, cast

from pydantic import BaseModel, ConfigDict, Field

from lirix import Lirix
from lirix.core.exceptions import LirixSecurityException

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

    def __init__(
        self,
        *,
        rpc_urls: Sequence[str],
        default_intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rpc_urls = list(rpc_urls)
        self.default_intent = default_intent
        self.state_delta_assertions = dict(state_delta_assertions or {})

    def _invoke_guardian(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        guardian = Lirix(rpc_urls=self.rpc_urls)
        resolved_intent = intent or self.default_intent or "unknown"
        merged_assertions = dict(self.state_delta_assertions)
        if state_delta_assertions is not None:
            merged_assertions.update(dict(state_delta_assertions))
        try:
            result = guardian.validate_and_simulate(
                resolved_intent,
                {"raw_intent_or_calldata": raw_intent_or_calldata, **merged_assertions, **kwargs},
            )
        except LirixSecurityException as exc:
            return str(exc.resolution_for_agent)
        if hasattr(result, "model_dump_json"):
            return str(cast(Any, result).model_dump_json())
        return str(result)

    def _run(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        return self._invoke_guardian(
            raw_intent_or_calldata,
            intent=intent,
            state_delta_assertions=state_delta_assertions,
            **kwargs,
        )

    async def _arun(
        self,
        raw_intent_or_calldata: str,
        intent: Optional[str] = None,
        state_delta_assertions: Optional[Mapping[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        result = await asyncio.to_thread(
            self._invoke_guardian,
            raw_intent_or_calldata,
            intent,
            state_delta_assertions,
            **kwargs,
        )
        return result
