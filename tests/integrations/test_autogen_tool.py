from __future__ import annotations

from typing import Any

from lirix.core.exceptions import LirixPolicyViolationException, LirixSecurityException
from lirix.integrations.autogen.tool import lirix_validate_intent


class DummyResult:
    def model_dump_json(self) -> str:
        return '{"validated": true}'


def test_test_autogen_tool(monkeypatch: Any) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        raise LirixSecurityException(
            resolution_agent=(
                "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
            )
        )

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)

    output = lirix_validate_intent(
        "swap 1 ETH for USDC",
        rpc_urls=["https://example-rpc.invalid"],
        intent="swap",
        state_delta_assertions={"assert_erc20_balance_increase": {"token": "0x1", "amount": 25}},
    )

    assert output == (
        "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
    )


def test_test_autogen_tool_2(monkeypatch: Any) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return DummyResult()

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)

    output = lirix_validate_intent(
        "swap 1 ETH for USDC",
        rpc_urls=["https://example-rpc.invalid"],
        intent="swap",
    )

    assert output == '{"validated": true}'


def test_test_autogen_tool_3(monkeypatch: Any) -> None:
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

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)

    output = lirix_validate_intent(
        "swap 1 ETH for USDC",
        rpc_urls=["https://example-rpc.invalid"],
        intent="swap",
    )

    assert output == (
        "Transaction Blocked by Lirix Policy: max_slippage_bps violated "
        "(expected=50, observed=250). "
        "Simulation result violates mandatory security policy. Abort execution."
    )
