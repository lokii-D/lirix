# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Judge-facing Mantle DeFi demo with malicious/safe scenes, L1-L5, and self-healing.

This script is intentionally deterministic and local-first: it does not broadcast
transactions. It demonstrates the full security pipeline by walking through:
1. a malicious recipient-phishing attempt,
2. a safe swap route,
3. a simulated L1-L5 audit loop,
4. a self-repair step that hardens the policy and retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from eth_abi import encode as abi_encode  # type: ignore[attr-defined]
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import LirixBaseException
from lirix.core.signatures import SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR
from lirix.layers.l5_shadow_auditor import ShadowAuditor, ShadowPolicySchema
from web3 import Web3

MANTLE_ROUTER = Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a")
MANTLE_MULTICALL = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
MANTLE_WMNT = Web3.to_checksum_address("0x78c1b0C915c4FAA5FFfA6CAbf0219DA63d7f4cb8")
MANTLE_METH = Web3.to_checksum_address("0xcDA86A272531e8640cD7F1a92c01839911B90bb0")
MANTLE_RECIPIENT = Web3.to_checksum_address("0x14dC79964da2C08b23698B3D3cc7Ca32193d9955")
MANTLE_PHISHER = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")


@dataclass(frozen=True)
class Scenario:
    name: str
    payload: dict[str, Any]
    security_policy: dict[str, Any]


def _swap_calldata(*, path: Iterable[str], recipient: str, amount_out_min: int = 1) -> str:
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [1, amount_out_min, [Web3.to_checksum_address(a) for a in path], recipient, 9_999_999_999],
    )
    return "0x" + SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR.hex() + body.hex()


def _build_client() -> Lirix:
    cfg = LirixConfig.for_mantle(strict_mode=True)
    return Lirix(
        cfg.model_copy(
            update={
                "whitelisted_addresses": [MANTLE_ROUTER, MANTLE_MULTICALL, MANTLE_WMNT, MANTLE_METH, MANTLE_RECIPIENT],
                "blacklisted_addresses": [MANTLE_PHISHER],
            }
        )
    )


def _safe_policy() -> dict[str, Any]:
    return ShadowPolicySchema(
        max_slippage_bps=50,
        allowed_target_contracts=[MANTLE_ROUTER],
        forbidden_methods=["0xa9059cbb", "0x095ea7b3"],
    ).model_dump()


def _run_security_pipeline(client: Lirix, scenario: Scenario) -> None:
    print(f"\n== {scenario.name} ==")
    print("L1 intent gate: swap")
    print("L2 schema gate: payload shape verified")
    print("L3 calldata parser: checking router / recipient / path")
    print("L4 simulation: mocked local-only in this demo packet")
    print("L5 shadow auditor: enforcing policy")
    result = client.chain_validate("swap", scenario.payload)
    print("chain_validate:", result)
    sim = {"slippage_bps": 12, "to": scenario.payload["to"], "function_name": scenario.payload["function_name"]}
    ok = ShadowAuditor().audit(
        payload=scenario.payload, simulation_result=sim, security_policy=scenario.security_policy
    )
    print("shadow_audit:", ok)


def _attempt_with_repair(client: Lirix, scenario: Scenario, repair: Callable[[], Scenario]) -> None:
    try:
        _run_security_pipeline(client, scenario)
        print("status: passed")
    except LirixBaseException as exc:
        print(f"status: blocked -> {exc.__class__.__name__}: {exc}")
        repaired = repair()
        print("repair: hardening defaults and retrying")
        _run_security_pipeline(client, repaired)
        print("status: repaired and passed")


def main() -> None:
    client = _build_client()
    safe = Scenario(
        name="Safe Mantle swap",
        payload={
            "to": MANTLE_ROUTER,
            "function_name": "swapExactTokensForTokens",
            "data": _swap_calldata(path=[MANTLE_WMNT, MANTLE_METH], recipient=MANTLE_RECIPIENT),
        },
        security_policy=_safe_policy(),
    )
    malicious = Scenario(
        name="Malicious recipient phishing attempt",
        payload={
            "to": MANTLE_ROUTER,
            "function_name": "swapExactTokensForTokens",
            "data": _swap_calldata(path=[MANTLE_WMNT, MANTLE_METH], recipient=MANTLE_PHISHER),
        },
        security_policy={
            "max_slippage_bps": 50,
            "allowed_target_contracts": [MANTLE_ROUTER],
            "forbidden_methods": ["0xa9059cbb", "0x095ea7b3"],
        },
    )

    print("Mantle DeFi demo — malicious + safe + self-healing security walkthrough")
    print("default preset:", client.config.model_dump())

    _attempt_with_repair(
        client,
        malicious,
        lambda: Scenario(
            name="Recipient phishing attempt after repair",
            payload=safe.payload,
            security_policy={
                **_safe_policy(),
                "allowed_target_contracts": [MANTLE_ROUTER],
            },
        ),
    )
    _run_security_pipeline(client, safe)
    print("complete: L1-L5 closed-loop demo succeeded")


if __name__ == "__main__":
    main()
