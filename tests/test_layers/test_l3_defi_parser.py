from __future__ import annotations

from typing import Any

import pytest
from eth_abi import encode as abi_encode
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import DeFiSlippageMissingException, MaliciousPayloadException
from lirix.core.hook_manager import HookManager
from lirix.core.multicall import MulticallEncoder
from lirix.core.signatures import AGGREGATE3_SELECTOR, AGGREGATE3_VALUE_SELECTOR
from lirix.layers.l3_defi_parser import DeFiPayloadParser
from web3 import Web3

from tests.test_layers.conftest import (
    SWAP_SELECTOR,
    addr_recipient,
    build_multicall_calldata,
    build_swap_calldata,
    mainnet_multicall,
    mainnet_router,
    malicious_dead,
    stack_nested_multicall,
    token_usdc,
    token_weth,
)


def _full_whitelist() -> list[str]:
    return sorted(
        {mainnet_router(), mainnet_multicall(), token_weth(), token_usdc(), addr_recipient()}
    )


def _parser_cfg(**kw: Any) -> LirixConfig:
    base: dict[str, Any] = {
        "chain_id": 1,
        "strict_mode": False,
        "allowed_intents": ["swap"],
        "allowed_function_names": ["swapExactTokensForTokens"],
        "allowed_to_addresses": [mainnet_router(), mainnet_multicall()],
        "whitelisted_addresses": _full_whitelist(),
        "blacklisted_addresses": [],
    }
    base.update(kw)
    return LirixConfig(**base)


def test_l3_data_exactly_zero_x_only() -> None:
    cfg = _parser_cfg()
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0x"}) is True


def test_l3_short_hex_blob_under_four_bytes() -> None:
    cfg = _parser_cfg()
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0x00"}) is True


def test_swap_with_zero_slippage_blocked() -> None:
    cfg = _parser_cfg()
    data = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=0,
    )
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_swap_with_valid_slippage_passed() -> None:
    cfg = _parser_cfg()
    data = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=1,
    )
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data}) is True


def test_l3_hex_fromhex_failure_odd_nibbles() -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException, match="not valid hex"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0x0"})


def test_l3_chain999_swap_hits_multicall_default_guard() -> None:
    cfg = LirixConfig(
        chain_id=999,
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[mainnet_router()],
        uniswap_v2_router=mainnet_router(),
    )
    data = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=1,
    )
    with pytest.raises(MaliciousPayloadException, match="Multicall3"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_l3_outer_generic_contract_unknown_selector() -> None:
    cfg = _parser_cfg()
    assert (
        DeFiPayloadParser(cfg).validate({"to": addr_recipient(), "data": "0x12345678" + "00" * 20})
        is True
    )


def test_l3_multicall_with_empty_inner_calldata_plus_swap() -> None:
    cfg = _parser_cfg()
    swap_b = bytes.fromhex(
        build_swap_calldata(
            path=[token_weth(), token_usdc()],
            recipient=addr_recipient(),
            amount_out_min=0,
        )[2:]
    )
    calls = [(mainnet_router(), False, b""), (mainnet_router(), False, swap_b)]
    data = build_multicall_calldata(calls)
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": data})


def test_l3_nested_inner_swap_wrong_router_target() -> None:
    cfg = _parser_cfg()
    swap_b = bytes.fromhex(
        build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())[2:]
    )
    calls = [(addr_recipient(), False, swap_b)]
    data = build_multicall_calldata(calls)
    with pytest.raises(MaliciousPayloadException, match="Nested swap must target"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": data})


def test_l3_swap_corrupt_inner_abi_body() -> None:
    cfg = _parser_cfg()
    body = SWAP_SELECTOR + b"\x01\x02"
    data = "0x" + body.hex()
    with pytest.raises(MaliciousPayloadException, match="Failed to decode swap calldata"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_l3_swap_happy_path() -> None:
    cfg = _parser_cfg(blacklisted_addresses=[])
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data}) is True


def test_l3_swap_with_empty_whitelist_ok() -> None:
    cfg = _parser_cfg(whitelisted_addresses=[])
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data}) is True


def test_l3_double_nested_multicall_then_swap() -> None:
    cfg = _parser_cfg()
    swap_b = bytes.fromhex(
        build_swap_calldata(
            path=[token_weth(), token_usdc()],
            recipient=addr_recipient(),
            amount_out_min=0,
        )[2:]
    )
    inner_mc = build_multicall_calldata([(mainnet_router(), False, swap_b)])
    inner_mc_b = bytes.fromhex(inner_mc[2:])
    double = build_multicall_calldata([(mainnet_multicall(), False, inner_mc_b)])
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": double})


def test_l3_multicall_nested_swap_happy_path() -> None:
    cfg = _parser_cfg(blacklisted_addresses=[])
    inner = bytes.fromhex(
        build_swap_calldata(
            path=[token_weth(), token_usdc()],
            recipient=addr_recipient(),
            amount_out_min=0,
        )[2:]
    )
    mc_data = build_multicall_calldata([(mainnet_router(), False, inner)])
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": mc_data})


def test_l3_decode_error_truncated_swap() -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException, match="Failed to decode swap calldata"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0x38ed173900"})


def test_l3_router_poison_non_swap_selector() -> None:
    cfg = _parser_cfg()
    with pytest.raises(
        MaliciousPayloadException, match="Non-swap calldata directed at Uniswap router"
    ):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0xdeadbeef00"})


def test_l3_multicall_poison_swap_shaped_on_multicall() -> None:
    cfg = _parser_cfg()
    swap = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    with pytest.raises(
        MaliciousPayloadException, match="Non-aggregate3 calldata directed at Multicall3"
    ):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": swap})


def test_l3_aggregate3_wrong_outer_target() -> None:
    cfg = _parser_cfg()
    empty_mc = build_multicall_calldata([])
    with pytest.raises(
        MaliciousPayloadException, match="aggregate3 calldata must target canonical"
    ):
        DeFiPayloadParser(cfg).validate(
            {
                "to": Web3.to_checksum_address("0x0000000000000000000000000000000000000001"),
                "data": empty_mc,
            }
        )


def test_l3_multicall_inner_target_poison() -> None:
    cfg = _parser_cfg()
    inner_mc = bytes.fromhex(build_multicall_calldata([])[2:])
    calls = [(addr_recipient(), False, inner_mc)]
    data = build_multicall_calldata(calls)
    with pytest.raises(
        MaliciousPayloadException, match="Nested aggregate3 call must target Multicall3"
    ):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": data})


def test_l3_multicall_inner_unknown_selector() -> None:
    cfg = _parser_cfg()
    junk = bytes.fromhex("deadbeef") + b"\x00" * 32
    calls = [(mainnet_router(), False, junk)]
    data = build_multicall_calldata(calls)
    with pytest.raises(MaliciousPayloadException, match="Unsupported inner call inside Multicall3"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": data})


def test_l3_blacklist_recipient_in_swap() -> None:
    bad = malicious_dead()
    cfg = _parser_cfg(blacklisted_addresses=[bad])
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=bad)
    with pytest.raises(MaliciousPayloadException, match="block-listed"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_l3_whitelist_miss_extra_token_touch() -> None:
    cfg = _parser_cfg(
        whitelisted_addresses=[
            mainnet_router(),
            mainnet_multicall(),
            token_weth(),
            addr_recipient(),
        ]
    )
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    with pytest.raises(MaliciousPayloadException, match="not in whitelisted_addresses"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_l3_swap_to_wrong_outer_contract() -> None:
    cfg = _parser_cfg()
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    with pytest.raises(MaliciousPayloadException, match="swap calldata must target canonical"):
        DeFiPayloadParser(cfg).validate({"to": addr_recipient(), "data": data})


def test_l3_multicall_decode_failure() -> None:
    cfg = _parser_cfg()
    bad = "0x82ad56cb" + "ff" * 12
    with pytest.raises(MaliciousPayloadException, match="Failed to decode Multicall3"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": bad})


def test_l3_to_not_string() -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException, match="to must be a string"):
        DeFiPayloadParser(cfg).validate({"to": 12345, "data": "0x"})  # type: ignore[dict-item]


def test_l3_unknown_chain_requires_overrides() -> None:
    cfg = LirixConfig(
        chain_id=999,
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[mainnet_router()],
    )
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    with pytest.raises(MaliciousPayloadException, match="uniswap_v2_router"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data})


def test_l3_unknown_chain_with_explicit_contracts() -> None:
    cfg = LirixConfig(
        chain_id=999,
        strict_mode=False,
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[mainnet_router()],
        multicall3_address=mainnet_multicall(),
        uniswap_v2_router=mainnet_router(),
        whitelisted_addresses=_full_whitelist(),
    )
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    assert DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": data}) is True


def test_l3_invalid_data_type() -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException, match="data must be a string"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": 12345})  # type: ignore[dict-item]


def test_l3_invalid_hex_data() -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException, match="not valid hex"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_router(), "data": "0xzz"})


def test_lirix_chain_validate_full_stack_happy() -> None:
    cfg = _parser_cfg(blacklisted_addresses=[])
    client = Lirix(cfg)
    data = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=0,
    )
    payload = {
        "to": mainnet_router(),
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": data,
    }
    with pytest.raises(DeFiSlippageMissingException):
        client.chain_validate("swap", payload)


def test_lirix_chain_validate_stops_at_l3() -> None:
    cfg = _parser_cfg(blacklisted_addresses=[addr_recipient()])
    client = Lirix(cfg)
    data = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    payload = {
        "to": mainnet_router(),
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": data,
    }
    with pytest.raises(MaliciousPayloadException):
        client.chain_validate("swap", payload)


@pytest.mark.parametrize(
    "_id,payload",
    [
        ("swap_truncated", {"to": mainnet_router(), "data": "0x38ed173900"}),
        ("router_junk_selector", {"to": mainnet_router(), "data": "0xcafebabe00"}),
        (
            "multicall_swap_mismatch",
            {
                "to": mainnet_multicall(),
                "data": build_swap_calldata(
                    path=[token_weth(), token_usdc()], recipient=addr_recipient()
                ),
            },
        ),
        ("aggregate_wrong_outer", {"to": mainnet_router(), "data": build_multicall_calldata([])}),
        (
            "inner_mc_poison",
            {
                "to": mainnet_multicall(),
                "data": build_multicall_calldata(
                    [(addr_recipient(), False, bytes.fromhex(build_multicall_calldata([])[2:]))]
                ),
            },
        ),
        (
            "inner_unknown_sel",
            {
                "to": mainnet_multicall(),
                "data": build_multicall_calldata(
                    [(mainnet_router(), False, bytes.fromhex("cafebabe"))]
                ),
            },
        ),
        (
            "blacklist_recipient",
            {
                "to": mainnet_router(),
                "data": build_swap_calldata(
                    path=[token_weth(), token_usdc()], recipient=malicious_dead()
                ),
            },
        ),
        ("data_not_string", {"to": mainnet_router(), "data": None}),  # type: ignore[dict-item]
    ],
)
def test_l3_malicious_matrix_raises(_id: str, payload: dict[str, Any]) -> None:
    cfg = _parser_cfg()
    with pytest.raises(MaliciousPayloadException):
        DeFiPayloadParser(cfg).validate(payload)


def test_l3_multicall_depth_six_guard_intercepted() -> None:
    cfg = _parser_cfg()
    deep = stack_nested_multicall(mainnet_multicall(), 6)
    with pytest.raises(MaliciousPayloadException, match="Multicall nesting depth"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": deep})


def test_l3_multicall_ten_layer_zip_bomb_intercepts_not_recursion_error() -> None:
    cfg = _parser_cfg()
    deep = stack_nested_multicall(mainnet_multicall(), 10)
    with pytest.raises(MaliciousPayloadException, match="Multicall nesting depth"):
        DeFiPayloadParser(cfg).validate({"to": mainnet_multicall(), "data": deep})


def test_l3_short_blob_invokes_layer_hook() -> None:
    cfg = _parser_cfg()
    mgr = HookManager()
    seen: list[str] = []

    def h(*args: object, **kwargs: object) -> None:
        seen.append("ok")

    from lirix.core.constants import HOOK_LAYER_L3

    mgr.register_hook(HOOK_LAYER_L3, h)
    assert (
        DeFiPayloadParser(cfg, hooks=mgr).validate({"to": mainnet_router(), "data": "0x00"}) is True
    )
    assert seen == ["ok"]


def test_l3_aggregate3_value_wrong_outer_to_raises() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    bogus = enc.encode_transactions([{"to": token_weth(), "data": "0x", "value": 1}])
    data = bogus["data"]
    assert data[2:10] == AGGREGATE3_VALUE_SELECTOR.hex()
    with pytest.raises(MaliciousPayloadException, match="aggregate3Value calldata must target"):
        DeFiPayloadParser(cfg).validate({"to": token_weth(), "data": data})


def test_l3_aggregate3_value_decode_walk_ok() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    outer = enc.encode_transactions([{"to": token_weth(), "data": "0x", "value": 2}])
    assert DeFiPayloadParser(cfg).validate({"to": mc, "data": outer["data"]}) is True


def test_l3_aggregate3_value_decode_failure() -> None:
    cfg = _parser_cfg()
    sel = AGGREGATE3_VALUE_SELECTOR.hex()
    with pytest.raises(MaliciousPayloadException, match="aggregate3Value"):
        DeFiPayloadParser(cfg).validate(
            {"to": mainnet_multicall(), "data": "0x" + sel + "deadbeef"}
        )


def test_l3_aggregate3_value_nested_inner_value_walk() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    inner = enc.encode_transactions([{"to": token_weth(), "data": "0x", "value": 1}])
    nested = enc.encode_transactions([{"to": mc, "data": inner["data"], "value": 0}])
    assert DeFiPayloadParser(cfg).validate({"to": mc, "data": nested["data"]}) is True


def test_l3_value_walk_recurse_into_aggregate3_on_mc() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    sw0 = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=0,
    )
    inner_agg3 = enc.encode_transactions([{"to": mainnet_router(), "data": sw0, "value": 0}])
    ibody = bytes.fromhex(inner_agg3["data"][2:])
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(mc, False, 0, ibody)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_value_walk_recurse_into_aggregate3_value_on_mc() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    sw0 = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=0,
    )
    inner_val = enc.encode_transactions(
        [
            {"to": mainnet_router(), "data": sw0, "value": 0},
            {"to": token_weth(), "data": "0x", "value": 1},
        ]
    )
    ibody = bytes.fromhex(inner_val["data"][2:])
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(mc, False, 0, ibody)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_aggregate3_value_inner_unknown_selector() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    inner = abi_encode(
        ["(address,bool,uint256,bytes)[]"], [[(token_weth(), False, 0, bytes.fromhex("cafebabe"))]]
    )
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(MaliciousPayloadException, match="Unsupported inner call"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_aggregate3_value_nested_aggregate3_wrong_router() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    weth = token_weth()
    faux = AGGREGATE3_SELECTOR + b"\x01" * 32
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(weth, False, 0, faux)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(MaliciousPayloadException, match="Nested aggregate3"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_aggregate3_value_nested_aggregate3_value_wrong_target() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    weth = token_weth()
    faux = AGGREGATE3_VALUE_SELECTOR + b"\x01" * 32
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(weth, False, 0, faux)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(MaliciousPayloadException, match="Nested aggregate3Value"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_aggregate3_value_inner_swap_walk() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    rt = mainnet_router()
    enc = MulticallEncoder(mc)
    sw = build_swap_calldata(
        path=[token_weth(), token_usdc()],
        recipient=addr_recipient(),
        amount_out_min=0,
    )
    outer = enc.encode_transactions(
        [{"to": rt, "data": sw, "value": 0}, {"to": token_weth(), "data": "0x", "value": 1}]
    )
    with pytest.raises(DeFiSlippageMissingException):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": outer["data"]})


def test_l3_walk_multicall_value_depth_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    import lirix.layers.l3_defi_parser as mod

    monkeypatch.setattr(mod, "MAX_MULTICALL_RECURSION_DEPTH", 0)
    cfg = _parser_cfg()
    p = DeFiPayloadParser(cfg)
    inner = abi_encode(
        ["(address,bool,uint256,bytes)[]"], [[(mainnet_multicall(), False, 0, b"\x12")]]
    )
    with pytest.raises(MaliciousPayloadException, match="depth"):
        p._walk_multicall_value(inner, set(), 1)


def test_l3_aggregate3_batch_inner_value_wrong_multicall_target() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    enc = MulticallEncoder(mc)
    inner_val = enc.encode_transactions([{"to": token_weth(), "data": "0x", "value": 1}])
    cdata = bytes.fromhex(inner_val["data"][2:])
    wrap = abi_encode(["(address,bool,bytes)[]"], [[(token_weth(), False, cdata)]])
    data = "0x" + AGGREGATE3_SELECTOR.hex() + wrap.hex()
    with pytest.raises(MaliciousPayloadException, match="Nested aggregate3Value"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_value_walk_inner_aggregate3_wrong_target() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    weth = token_weth()
    faux = AGGREGATE3_SELECTOR + b"\x02" * 40
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(weth, False, 0, faux)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(MaliciousPayloadException, match="Nested aggregate3"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})


def test_l3_value_walk_inner_swap_wrong_router() -> None:
    cfg = _parser_cfg()
    mc = mainnet_multicall()
    weth = token_weth()
    swap_body = build_swap_calldata(path=[token_weth(), token_usdc()], recipient=addr_recipient())
    inner_b = bytes.fromhex(swap_body[2:])
    inner = abi_encode(["(address,bool,uint256,bytes)[]"], [[(weth, False, 0, inner_b)]])
    data = "0x" + AGGREGATE3_VALUE_SELECTOR.hex() + inner.hex()
    with pytest.raises(MaliciousPayloadException, match="Nested swap"):
        DeFiPayloadParser(cfg).validate({"to": mc, "data": data})
