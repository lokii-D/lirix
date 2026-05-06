from __future__ import annotations

import asyncio
from typing import Any

import pytest
from lirix.core.exceptions import LirixSimulationError
from lirix.core.guard import LirixGuard


@pytest.mark.asyncio
async def test_guard_rejects_non_list_args_when_signature_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = LirixGuard(rpc_url="http://example.invalid")
    monkeypatch.setattr(guard._schema_validator, "validate", lambda draft: True)
    with pytest.raises(LirixSimulationError, match="LRX_SIM_ARGS_TYPE"):
        await guard._parse_impl(
            {
                "to": "0x0000000000000000000000000000000000000001",
                "function_signature": "transfer(address,uint256)",
                "args": {"not": "a list"},
            }
        )


@pytest.mark.asyncio
async def test_guard_runs_state_delta_validator_when_assertions_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guard = LirixGuard(rpc_url="http://example.invalid")
    monkeypatch.setattr(guard._schema_validator, "validate", lambda draft: True)
    monkeypatch.setattr(guard._builder, "build", lambda signature, args: "0xdeadbeef")

    class _Sim:
        _w3 = object()

        async def async_run_simulation(
            self, target: str, calldata: str, sender: Any = None, value: int = 0
        ) -> dict[str, Any]:
            await asyncio.sleep(0)
            return {"ok": True}

    called = {"value": False}

    class _Validator:
        def __init__(self, w3: Any) -> None:
            self.w3 = w3

        async def validate(self, draft: dict[str, Any]) -> None:
            called["value"] = True

    guard._simulator = _Sim()  # noqa: SLF001
    monkeypatch.setattr("lirix.core.guard.StateDeltaValidator", _Validator)
    draft = {
        "to": "0x0000000000000000000000000000000000000001",
        "function_signature": "ping()",
        "args": [],
        "assertions": {"expect": "something"},
    }
    assert await guard._parse_impl(draft) is True
    assert called["value"] is True
