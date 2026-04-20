# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from hexbytes import HexBytes
from lirix.core.config import LirixConfig
from lirix.core.exceptions import (
    ContractPausedException,
    RPCUnavailableException,
    SimulationFailedException,
)
from lirix.layers.l5_sandbox_simulator import (
    SandboxSimulator,
    _hex_to_bytes,
    _normalize_revert_payload,
    evm_revert_to_natural_language,
)
from web3 import Web3
from web3.exceptions import ContractLogicError, Web3Exception


def _boom_calldata() -> str:
    return "0xa169ce09"


def test_evm_revert_error_string() -> None:
    # Error("hi") style payload fragment (selector + abi tail)
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    body: bytes = abi_encode(["string"], ["hello"])
    data = "0x08c379a0" + body.hex()
    msg = evm_revert_to_natural_language(data)
    assert "hello" in msg


def test_evm_revert_panic() -> None:
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    body: bytes = abi_encode(["uint256"], [0x11])
    data = "0x4e487b71" + body.hex()
    msg = evm_revert_to_natural_language(data)
    assert "panic" in msg.lower() or "overflow" in msg.lower()


def test_evm_revert_custom_selector() -> None:
    data = "0xdeadbeef12345678"
    msg = evm_revert_to_natural_language(data)
    assert "custom" in msg.lower()


def test_evm_revert_none_and_short() -> None:
    assert "without" in evm_revert_to_natural_language(None).lower()
    assert "without" in evm_revert_to_natural_language("0x010203").lower()


def test_evm_revert_dict_payload() -> None:
    _d = (
        "0x08c379a0000000000000000000000000000000000000000000000000000000000000002"
        "000000000000000000000000000000000000000000000000000000000000000003"
        "616263000000000000000000000000000000000000000000000000000000000000"
    )
    msg = evm_revert_to_natural_language({"data": _d})
    assert "abc" in msg or "revert" in msg.lower()


def test_evm_revert_dict_non_string_inner() -> None:
    msg = evm_revert_to_natural_language({"data": cast(Any, 123)})
    assert "without" in msg.lower()


def test_evm_revert_invalid_hex_string() -> None:
    msg = evm_revert_to_natural_language("0xzz")
    assert "without" in msg.lower()


def test_hex_to_bytes_prepends_0x() -> None:
    raw = _hex_to_bytes("cafe")  # noqa: SLF001
    assert raw == bytes.fromhex("cafe")


def test_normalize_revert_payload_non_str_non_dict() -> None:
    assert _normalize_revert_payload(cast(Any, 42)) is None  # noqa: SLF001


def test_decode_error_string_empty_message() -> None:
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    body: bytes = abi_encode(["string"], [""])
    data = "0x08c379a0" + body.hex()
    msg = evm_revert_to_natural_language(data)
    assert "empty" in msg.lower()


def test_decode_panic_unknown_code() -> None:
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    body: bytes = abi_encode(["uint256"], [0xABCDEF])
    data = "0x4e487b71" + body.hex()
    msg = evm_revert_to_natural_language(data)
    assert "panic" in msg.lower()


def test_decode_panic_corrupt_body() -> None:
    msg = evm_revert_to_natural_language("0x4e487b71dead")
    assert "decoded" in msg.lower() or "panic" in msg.lower()


def test_build_tx_with_from_address() -> None:
    sim = SandboxSimulator()
    tx = sim._build_call_tx(  # noqa: SLF001
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "data": "0x",
            "value": 0,
            "from": "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955",
        }
    )
    assert tx["from"] == "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"


def test_simulate_empty_return_data() -> None:
    w3 = MagicMock()
    w3.eth.call = MagicMock(return_value=b"")
    sim = SandboxSimulator()
    out = sim.simulate(
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "data": "0x",
            "value": 0,
        },
        web3=w3,
        block_number=1,
    )
    assert out["return_data"] == "0x"


def test_decode_error_string_corrupt() -> None:
    msg = evm_revert_to_natural_language("0x08c379a0ffff")
    assert "decode" in msg.lower() or "could not" in msg.lower()


def test_simulate_success() -> None:
    w3 = MagicMock()
    w3.eth.call = MagicMock(return_value=b"\x01\x02")
    sim = SandboxSimulator()
    out = sim.simulate(
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "data": "0x",
            "value": 0,
        },
        web3=w3,
        block_number=1,
    )
    assert out["simulation_ok"] is True
    assert out["return_data"] == "0x0102"


def test_simulate_contract_logic_error() -> None:
    w3 = MagicMock()
    w3.eth.call = MagicMock(
        side_effect=ContractLogicError(
            "revert",
            data="0x08c379a0000000000000000000000000000000000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000036162630000000000000000000000000000000000000000000000000000000000",
        )
    )
    sim = SandboxSimulator()
    with pytest.raises(SimulationFailedException) as ei:
        sim.simulate(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": "0x",
                "value": 0,
            },
            web3=w3,
            block_number=3,
        )
    assert "abc" in ei.value.human_readable_reason


def test_simulate_web3_rpc_error() -> None:
    w3 = MagicMock()

    class _E(Web3Exception):
        pass

    w3.eth.call = MagicMock(side_effect=_E("rpc"))
    sim = SandboxSimulator()
    with pytest.raises(RPCUnavailableException):
        sim.simulate(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": "0x",
                "value": 0,
            },
            web3=w3,
            block_number=1,
        )


def test_simulate_contract_paused_translation() -> None:
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    w3 = MagicMock()
    data = "0x08c379a0" + abi_encode(["string"], ["Pausable: paused"]).hex()
    w3.eth.call = MagicMock(side_effect=ContractLogicError("revert", data=data))
    sim = SandboxSimulator()
    with pytest.raises(ContractPausedException):
        sim.simulate(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": "0x",
                "value": 0,
            },
            web3=w3,
            block_number=3,
        )


def test_build_tx_invalid() -> None:
    sim = SandboxSimulator()
    with pytest.raises(SimulationFailedException):
        sim.simulate({"to": 1, "data": "0x", "value": 0}, web3=MagicMock(), block_number=1)
    with pytest.raises(SimulationFailedException):
        sim.simulate(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": 123,
                "value": 0,
            },
            web3=MagicMock(),
            block_number=1,
        )
    with pytest.raises(SimulationFailedException):
        sim.simulate(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": "0x",
                "value": "x",
            },
            web3=MagicMock(),
            block_number=1,
        )


def test_simulate_async_success() -> None:
    async def _run() -> None:
        aw3 = MagicMock()
        aw3.eth.call = AsyncMock(return_value=b"")
        sim = SandboxSimulator()
        out = await sim.simulate_async(
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "data": "0x",
                "value": 0,
            },
            async_web3=aw3,
            block_number=1,
        )
        assert out["simulation_ok"] is True

    asyncio.run(_run())


def test_simulate_async_wrapped() -> None:
    async def _run() -> None:
        aw3 = MagicMock()
        aw3.eth.call = AsyncMock(
            side_effect=ContractLogicError(
                "x",
                data="0x08c379a000000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000003xx0000000000000000000000000000000000000000000000000000000000000000",
            )
        )
        sim = SandboxSimulator()
        with pytest.raises(SimulationFailedException):
            await sim.simulate_async(
                {
                    "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                    "data": "0x",
                    "value": 0,
                },
                async_web3=aw3,
                block_number=1,
            )

    asyncio.run(_run())


def test_simulate_async_contract_paused_translation() -> None:
    from eth_abi import encode as abi_encode  # type: ignore[attr-defined]

    async def _run() -> None:
        aw3 = MagicMock()
        data = "0x08c379a0" + abi_encode(["string"], ["Pausable: paused"]).hex()
        aw3.eth.call = AsyncMock(side_effect=ContractLogicError("revert", data=data))
        sim = SandboxSimulator()
        with pytest.raises(ContractPausedException):
            await sim.simulate_async(
                {
                    "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                    "data": "0x",
                    "value": 0,
                },
                async_web3=aw3,
                block_number=3,
            )

    asyncio.run(_run())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _anvil_json_rpc(url: str, method: str, params: list[object]) -> dict[str, object]:
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(  # noqa: S310 — 测试仅本地 loopback
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return cast(dict[str, object], json.loads(resp.read().decode()))
    except urllib.error.URLError as exc:
        raise AssertionError(f"anvil unreachable: {exc}") from exc


def test_anvil_revert_message_accuracy() -> None:
    """集成：真实 eth_call 回滚与 Error(string) 解析一致（需本地 Anvil）。"""
    rpc = "http://127.0.0.1:18545"
    artifact = _repo_root() / "out" / "Reverter.sol" / "Reverter.json"
    if not artifact.is_file():
        pytest.skip("forge build artifact missing; run `forge build` first")

    proc = subprocess.Popen(
        ["anvil", "--port", "18545", "--silent"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                r = _anvil_json_rpc(rpc, "eth_blockNumber", [])
                if r.get("result"):
                    break
            except AssertionError:
                time.sleep(0.1)
        else:
            pytest.fail("anvil did not start")

        raw = json.loads(artifact.read_text())
        code = raw["deployedBytecode"]["object"]
        target = "0x00000000000000000000000000000000000000f0"
        res = _anvil_json_rpc(rpc, "anvil_setCode", [target, code])
        if res.get("error"):
            pytest.skip(f"anvil_setCode not supported: {res['error']}")

        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        sim = SandboxSimulator()
        with pytest.raises(SimulationFailedException) as ei:
            sim.simulate(
                {"to": target, "data": _boom_calldata(), "value": 0},
                web3=w3,
                block_number=int(w3.eth.block_number),
            )
        assert "sandbox_fail" in ei.value.human_readable_reason
        assert "sandbox_fail" in ei.value.context.get("revert_semantics", "")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_lirix_validate_and_simulate_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix import Lirix
    from lirix.layers.l4_rpc_manager import RPCManager

    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["http://mock:8545"],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[
            "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        ],
    )
    lix = Lirix(cfg)

    def fake_reconcile(self: RPCManager) -> int:
        return 1

    def fake_web3(self: RPCManager) -> Web3:
        w = MagicMock()
        w.eth = MagicMock()
        w.eth.call = MagicMock(return_value=b"")
        return w

    monkeypatch.setattr(RPCManager, "sync_reconcile", fake_reconcile)
    monkeypatch.setattr(RPCManager, "sync_web3", fake_web3)

    out = lix.validate_and_simulate(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": "0x",
            "value": 0,
        },
    )
    assert out["validated"] is True
    assert out["simulation_ok"] is True


def test_lirix_async_validate_and_simulate(monkeypatch: pytest.MonkeyPatch) -> None:
    from lirix import Lirix
    from lirix.layers.l4_rpc_manager import RPCManager

    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["http://mock:8545"],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[
            "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        ],
    )
    lix = Lirix(cfg)

    async def fake_reconcile(self: RPCManager) -> int:
        return 2

    def fake_aw3(self: RPCManager) -> Web3:
        w = MagicMock()
        w.eth.call = AsyncMock(return_value=b"\xab")
        w.to_checksum_address = Web3.to_checksum_address
        return cast(Web3, w)

    monkeypatch.setattr(RPCManager, "async_reconcile", fake_reconcile)
    monkeypatch.setattr(RPCManager, "async_web3", fake_aw3)

    async def _run() -> dict[str, object]:
        return await lix.async_validate_and_simulate(
            "swap",
            {
                "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "function_name": "swapExactTokensForTokens",
                "data": "0x",
                "value": 0,
            },
        )

    out = asyncio.run(_run())
    assert out["validated"] is True


def test_state_override_balance_void_mint_passes_through_eth_call() -> None:
    """虚空印钞：无 override 时模拟因余额不足回滚；带 balance state override 时放行并校验透传。"""
    from_addr = Web3.to_checksum_address("0x1111111111111111111111111111111111111111")
    to_addr = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
    one_eth_hex = "0xDE0B6B3A7640000"
    overrides: dict[str, dict[str, str]] = {from_addr: {"balance": one_eth_hex}}

    captured: list[dict[str, object]] = []

    def fake_eth_call(
        transaction: object,
        block_identifier: object = None,
        state_override: object = None,
        ccip_read_enabled: object = None,
    ) -> HexBytes:
        captured.append(
            {
                "state_override": state_override,
                "block_identifier": block_identifier,
            }
        )
        if state_override is None:
            raise ContractLogicError(
                "insufficient funds for intrinsic transaction cost",
                data="0x",
            )
        assert isinstance(state_override, dict)
        entry = state_override.get(from_addr) or state_override.get(
            Web3.to_checksum_address(from_addr)
        )
        assert entry is not None
        assert entry.get("balance") == one_eth_hex
        return HexBytes(b"\x01\x02")

    w3 = MagicMock()
    w3.eth.call = fake_eth_call
    sim = SandboxSimulator()
    payload = {
        "to": to_addr,
        "data": "0x",
        "value": 10**18,
        "from": from_addr,
    }

    with pytest.raises(SimulationFailedException):
        sim.simulate(payload, web3=w3, block_number=7, state_overrides=None)

    out = sim.simulate(payload, web3=w3, block_number=7, state_overrides=cast(Any, overrides))
    assert out["simulation_ok"] is True
    assert captured[-1]["state_override"] == overrides
    assert captured[-1]["block_identifier"] == 7


def test_async_state_override_passed_to_eth_call() -> None:
    async def _run() -> None:
        from_addr = Web3.to_checksum_address("0x2222222222222222222222222222222222222222")
        to_addr = Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D")
        ov = {from_addr: {"balance": "0x1"}}
        seen: dict[str, object] = {}

        async def fake_call(
            transaction: object,
            block_identifier: object = None,
            state_override: object = None,
            ccip_read_enabled: object = None,
        ) -> bytes:
            seen["state_override"] = state_override
            return b""

        aw3 = MagicMock()
        aw3.eth.call = fake_call
        sim = SandboxSimulator()
        await sim.simulate_async(
            {
                "to": to_addr,
                "data": "0x",
                "value": 0,
                "from": from_addr,
            },
            async_web3=aw3,
            block_number=9,
            state_overrides=cast(Any, ov),
        )
        assert seen["state_override"] == ov

    asyncio.run(_run())


def test_lirix_validate_and_simulate_forwards_state_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lirix import Lirix
    from lirix.layers.l4_rpc_manager import RPCManager

    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=["http://mock:8545"],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[
            "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        ],
    )
    lix = Lirix(cfg)
    captured: dict[str, object] = {}

    def fake_reconcile(self: RPCManager) -> int:
        return 1

    def fake_web3(self: RPCManager) -> Web3:
        w = MagicMock()
        w.eth = MagicMock()
        w.eth.call = MagicMock(return_value=b"")
        return cast(Web3, w)

    def fake_simulate(
        self: object,
        payload: object,
        *,
        web3: object,
        block_number: int,
        state_overrides: object = None,
    ) -> dict[str, object]:
        captured["state_overrides"] = state_overrides
        return {
            "layer": "L5",
            "simulation_ok": True,
            "block_number": block_number,
            "return_data": "0x",
        }

    monkeypatch.setattr(RPCManager, "sync_reconcile", fake_reconcile)
    monkeypatch.setattr(RPCManager, "sync_web3", fake_web3)
    monkeypatch.setattr(SandboxSimulator, "simulate", fake_simulate)

    ov = {"0x1111111111111111111111111111111111111111": {"balance": "0xDE0B6B3A7640000"}}
    lix.validate_and_simulate(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": "0x",
            "value": 0,
        },
        state_overrides=ov,
    )
    assert captured["state_overrides"] == ov


def test_simulate_async_rpc_error() -> None:
    async def _run() -> None:
        aw3 = MagicMock()

        class _E(Web3Exception):
            pass

        aw3.eth.call = AsyncMock(side_effect=_E("bad"))
        sim = SandboxSimulator()
        with pytest.raises(RPCUnavailableException):
            await sim.simulate_async(
                {
                    "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                    "data": "0x",
                    "value": 0,
                },
                async_web3=aw3,
                block_number=1,
            )

    asyncio.run(_run())
