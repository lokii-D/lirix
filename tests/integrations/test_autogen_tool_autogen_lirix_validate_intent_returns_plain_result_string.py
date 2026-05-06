from __future__ import annotations

from typing import Any

from lirix.integrations.autogen.tool import alirix_validate_intent, lirix_validate_intent


def test_test_autogen_tool_autogen_lirix_validate_intent_returns_plain_result_string(
    monkeypatch: Any,
) -> None:
    def fake_validate_and_simulate(self: Any, intent: str, payload: Any, **kwargs: Any) -> Any:
        return {"ok": True}

    monkeypatch.setattr("lirix.Lirix.validate_and_simulate", fake_validate_and_simulate)
    out = lirix_validate_intent("payload", rpc_urls=["https://rpc.invalid"], intent="swap")
    assert out == "{'ok': True}"


async def test_autogen_async_wrapper_delegates_to_thread(monkeypatch: Any) -> None:
    async def fake_to_thread(func, *args):
        return func(*args)

    monkeypatch.setattr("lirix.integrations.autogen.tool.asyncio.to_thread", fake_to_thread)
    out = await alirix_validate_intent("payload", ["https://rpc.invalid"], intent="swap")
    assert isinstance(out, str)
