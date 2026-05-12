# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Internal: Multicall3 batch encoding + validate_only-gated audit (re-exported from lirix)."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from web3 import Web3

from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_MULTICALL_PACK
from lirix.core.exceptions import ConfigurationGuardException, MulticallEncodingException
from lirix.core.multicall import MulticallEncoder
from lirix.core.signatures import AGGREGATE3_SELECTOR, AGGREGATE3_VALUE_SELECTOR


def _resolve_multicall3_address(config: Any) -> str:
    if config.multicall3_address:
        return str(config.multicall3_address)
    if config.chain_id == 1:
        return Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    raise ConfigurationGuardException(
        human_readable_reason=(
            "atomic_multicall requires multicall3_address for non-mainnet chain_id."
        ),
        context={"chain_id": config.chain_id},
    )


def atomic_multicall(
    client: Any,
    intent: str,
    transactions: Sequence[Mapping[str, Any]],
    *,
    outer_value_wei: Optional[int] = None,
) -> Dict[str, Any]:
    """将多笔子交易原子编码为 Multicall3 单笔 calldata，并走与 validate_only 同构的 L1→L3 取证。"""
    mc = _resolve_multicall3_address(client.config)
    encoder = MulticallEncoder(mc)
    encoded = encoder.encode_transactions(
        [dict(x) for x in transactions],
        outer_value_wei=outer_value_wei,
    )
    client.hooks.invoke_hooks_isolated(
        HOOK_MULTICALL_PACK,
        encoded=encoded,
        subcall_count=len(transactions),
        timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
    )
    data = encoded["data"]
    sel = bytes.fromhex(data[2:10])
    if sel == AGGREGATE3_VALUE_SELECTOR:
        fn = "aggregate3Value"
    elif sel == AGGREGATE3_SELECTOR:
        fn = "aggregate3"
    else:
        raise MulticallEncodingException(
            human_readable_reason="Encoded calldata selector is not Multicall3 aggregate3 family.",
            context={"selector": data[2:10]},
        )
    payload = {
        "to": encoded["to"],
        "data": encoded["data"],
        "value": encoded["value"],
        "function_name": fn,
    }
    validation = client.validate_only(intent, payload)
    return {
        "encoded": encoded,
        "payload": payload,
        "replay_bundle": validation["replay_bundle"],
        "validation_session": validation["validation_session"],
        "forensic_bundle": validation["forensic_bundle"],
        "security_trace": validation["security_trace"],
        "evidence_schema_version": validation["evidence_schema_version"],
        "evidence_v2": validation["evidence_v2"],
        "migration_modes": validation["migration_modes"],
    }
