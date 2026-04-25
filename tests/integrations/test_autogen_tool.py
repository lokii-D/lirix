from __future__ import annotations

from typing import Any

from lirix import Lirix
from lirix.core.exceptions import LirixSecurityException
from lirix.integrations.autogen.tool import lirix_validate_intent


class DummyResult:
    def model_dump_json(self) -> str:
        return '{"validated": true}'


def test_autogen_function_returns_remediation(monkeypatch: Any) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        raise LirixSecurityException(
            resolution_agent=(
                "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
            )
        )

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)

    output = lirix_validate_intent(
        "swap 1 ETH for USDC",
        rpc_urls=["https://example-rpc.invalid"],
        intent="swap",
        state_delta_assertions={"assert_erc20_balance_increase": {"token": "0x1", "amount": 25}},
    )

    assert output == (
        "Honeypot detected. Rewrite the route with a verified token pair and slippage cap."
    )


def test_autogen_function_serializes_success(monkeypatch: Any) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return DummyResult()

    monkeypatch.setattr(Lirix, "validate_and_simulate", fake_validate_and_simulate)

    output = lirix_validate_intent(
        "swap 1 ETH for USDC",
        rpc_urls=["https://example-rpc.invalid"],
        intent="swap",
    )

    assert output == '{"validated": true}'
