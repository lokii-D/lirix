# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix import Lirix, LirixConfig, atomic_multicall, register_hook
from lirix.core.constants import HOOK_LAYER_L1, HOOK_MULTICALL_PACK, HOOK_PRE_VALIDATE
from lirix.core.exceptions import (
    ConfigurationGuardException,
    MulticallEncodingException,
    RPCUnavailableException,
)
from lirix.core.hook_manager import HookManager
from lirix.core.multicall import MulticallEncoder
from lirix.layers.l4_rpc_manager import RPCManager
from tests.conftest import RPC_URL_UNREACHABLE_HIGH_PORT
from tests.test_layers.conftest import (
    addr_recipient,
    build_swap_calldata,
    mainnet_multicall,
    mainnet_router,
    token_usdc,
    token_weth,
)
from web3 import Web3
from web3 import types as web3_types
from web3.exceptions import ContractLogicError


def test_register_hook_helper_wires_pre_validate_hook() -> None:
    mgr = HookManager()
    seen: list[int] = []

    def cb(*args: object, **kwargs: object) -> None:
        seen.append(1)

    register_hook(mgr, HOOK_PRE_VALIDATE, cb)
    mgr.invoke_hooks(HOOK_PRE_VALIDATE)
    assert seen == [1]


def test_atomic_multicall_requires_explicit_multicall_address_on_unknown_chain() -> None:
    cfg = LirixConfig(
        chain_id=42,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mainnet_multicall(), token_weth()],
        whitelisted_addresses=sorted({mainnet_multicall(), token_weth()}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    with pytest.raises(ConfigurationGuardException, match="multicall3_address"):
        atomic_multicall(
            client,
            "swap",
            [{"to": token_weth(), "data": "0x"}],
        )


def test_atomic_multicall_rejects_encoder_output_to_non_multicall_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mc = mainnet_multicall()
    weth = token_weth()
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mc, weth],
        whitelisted_addresses=sorted({mc, weth}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)

    def fake_encode(
        self: MulticallEncoder,
        txs: object,
        **kw: object,
    ) -> dict[str, object]:  # noqa: ARG002
        return {
            "to": mc,
            "data": "0xdeadbeef",
            "value": 0,
            "access_list": [],
        }

    monkeypatch.setattr(MulticallEncoder, "encode_transactions", fake_encode)
    with pytest.raises(MulticallEncodingException, match="not Multicall3"):
        atomic_multicall(client, "swap", [{"to": weth, "data": "0x"}])


def test_atomic_multicall_selects_aggregate3value_when_subcall_has_value() -> None:
    mc = mainnet_multicall()
    weth = token_weth()
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3", "aggregate3Value"],
        allowed_to_addresses=[mc, weth],
        whitelisted_addresses=sorted({mc, weth}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    out = atomic_multicall(
        client,
        "swap",
        [{"to": weth, "data": "0x", "value": 1}],
    )
    assert out["payload"]["function_name"] == "aggregate3Value"


def test_atomic_multicall_uses_configured_multicall_address_on_custom_chain() -> None:
    mc = mainnet_multicall()
    weth = token_weth()
    cfg = LirixConfig(
        chain_id=99999,
        strict_mode=False,
        rpc_urls=[],
        multicall3_address=mc,
        uniswap_v2_router=mainnet_router(),
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mc, weth],
        whitelisted_addresses=sorted({mc, weth}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    out = atomic_multicall(client, "swap", [{"to": weth, "data": "0x"}])
    assert out["encoded"]["to"] == mc


def test_atomic_multicall_emits_pack_hook_with_encoded_payload() -> None:
    mc = mainnet_multicall()
    weth = token_weth()
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mc, weth],
        whitelisted_addresses=sorted({mc, weth}),
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)
    seen_pack: list[object] = []

    def on_pack(*args: object, **kwargs: object) -> None:
        seen_pack.append(kwargs.get("encoded"))

    client.hooks.register_hook(HOOK_MULTICALL_PACK, on_pack)
    out = atomic_multicall(
        client,
        "swap",
        [{"to": weth, "data": "0x"}],
    )
    assert out["encoded"]["to"] == mc
    assert seen_pack and isinstance(seen_pack[0], dict)


def test_chain_validate_survives_noncritical_l1_hook_exception() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=[
            "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955",
        ],
        blacklisted_addresses=[],
    )
    client = Lirix(cfg)

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("hook noise")

    client.hooks.register_hook(HOOK_LAYER_L1, boom)
    swap_data = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
    )
    assert client.chain_validate(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": swap_data,
        },
    )


def test_rpc_manager_reconcile_raises_when_all_rpcs_unavailable() -> None:
    cfg = LirixConfig(
        chain_id=1,
        rpc_urls=[RPC_URL_UNREACHABLE_HIGH_PORT],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
    )
    mgr = RPCManager(cfg)
    with pytest.raises(RPCUnavailableException):
        mgr.sync_reconcile()


def test_multicall3_aggregate3_reverts_atomically_on_invalid_subcall(
    deploy_multicall3_locally: Web3,
) -> None:
    """无 fork：Multicall3 由 fixture 注入；子调用 INVALID 时整笔 aggregate3 原子回滚。"""
    w3 = deploy_multicall3_locally
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    acct = w3.eth.accounts[0]
    ok = enc.encode_transactions([{"to": acct, "data": "0x"}])
    raw = w3.eth.call({"to": ok["to"], "data": ok["data"]})
    assert raw is not None

    revert_addr = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")
    w3.provider.make_request(web3_types.RPCEndpoint("anvil_setCode"), [revert_addr, "0xfe"])
    bad = enc.encode_transactions(
        [
            {"to": acct, "data": "0x"},
            {"to": revert_addr, "data": "0x"},
        ]
    )
    with pytest.raises(ContractLogicError):
        w3.eth.call({"to": bad["to"], "data": bad["data"]})
