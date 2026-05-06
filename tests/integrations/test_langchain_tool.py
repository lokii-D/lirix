from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix import Lirix
from lirix.core.exceptions import LirixPolicyViolationException, LirixSecurityException
from lirix.integrations.langchain.tool import LirixSecurityValidator


class DummyResult:
    def model_dump_json(self) -> str:
        return '{"validated": true}'


def test_test_langchain_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        raise LirixSecurityException(
            resolution_agent=(
                "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
            ),
            context={"intent": intent, "payload": payload},
        )

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)

    tool = LirixSecurityValidator(
        rpc_urls=["https://example-rpc.invalid"],
        default_intent="swap",
        state_delta_assertions={"assert_erc20_balance_increase": {"token": "0x1", "amount": 25}},
    )

    output = asyncio.run(
        tool._arun(
            "swap 1 ETH for USDC",
            intent="swap",
            state_delta_assertions={
                "assert_erc20_balance_increase": {"token": "0x2", "amount": 50}
            },
        )
    )

    assert output == (
        "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
    )


def test_test_langchain_tool_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return DummyResult()

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)

    tool = LirixSecurityValidator(rpc_urls=["https://example-rpc.invalid"], default_intent="swap")
    output = tool._run("swap 1 ETH for USDC")

    assert output == '{"validated": true}'


def test_test_langchain_tool_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        raise LirixPolicyViolationException(
            error_code="LRX_SHADOW_POLICY_BLOCKED",
            resolution_agent=(
                "Simulation result violates mandatory security policy. Abort execution."
            ),
            context={
                "policy_key": "max_slippage_bps",
                "expected": 50,
                "observed": 250,
            },
        )

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)

    tool = LirixSecurityValidator(rpc_urls=["https://example-rpc.invalid"], default_intent="swap")
    output = tool._run("swap 1 ETH for USDC")

    assert output == (
        "Transaction Blocked by Lirix Policy: max_slippage_bps violated "
        "(expected=50, observed=250). "
        "Simulation result violates mandatory security policy. Abort execution."
    )
