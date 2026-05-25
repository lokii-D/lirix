from __future__ import annotations

import json
import os

from eth_abi import encode as abi_encode
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import LirixSecurityException
from lirix.layers.l5_shadow_auditor import ShadowPolicySchema
from web3 import Web3

MANTLE_MOEROUTER = Web3.to_checksum_address("0xeaEE7EE68874218c3558b40063c42B82D3E7232a")
MANTLE_WMNT = Web3.to_checksum_address("0x78c1b0C915c4FAA5FFfA6CAbf0219DA63d7f4cb8")
MANTLE_USDY = Web3.to_checksum_address("0x5bE26527e817998A7206475496fDE1E68957c5A6")
PHISHING_RECIPIENT = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")
SAFE_RECIPIENT = Web3.to_checksum_address("0x0000000000000000000000000000000000000001")


def build_moe_swap_calldata(amount_out_min: int = 0, recipient: str = PHISHING_RECIPIENT) -> str:
    selector = bytes.fromhex("d004f0f8")
    body = abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [1, amount_out_min, [MANTLE_WMNT, MANTLE_USDY], recipient, 0],
    )
    return "0x" + (selector + body).hex()


def _build_config() -> LirixConfig:
    rpc_urls = os.getenv(
        "MANTLE_RPC_URLS",
        "https://rpc.mantle.xyz,https://mantle.drpc.org,https://rpc.ankr.com/mantle",
    ).split(",")
    update = {
        "rpc_urls": [u.strip() for u in rpc_urls if u.strip()],
        "allowed_intents": ["swap"],
        "allowed_function_names": ["swap", "exactInput", "exactOutput"],
    }
    return LirixConfig.for_mantle(strict_mode=True).model_copy(update=update)


def _policy() -> ShadowPolicySchema:
    return ShadowPolicySchema(
        max_slippage_bps=50,
        forbidden_methods=["approve", "setApprovalForAll"],
        allowed_target_contracts="ANY",
    )


def _print_case(title: str, payload: dict[str, object], repair_hint: str | None = None) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, default=str))
    if repair_hint:
        print(repair_hint)


def _run(client: Lirix, payload: dict[str, object], policy: ShadowPolicySchema, *, repair: bool = False) -> None:
    try:
        client.chain_validate("swap", payload)
        print("L1-L3: passed")
    except LirixSecurityException as exc:
        print(f"Blocked at validation: {exc}")
        return
    try:
        result = client.validate_and_simulate("swap", payload, security_policy=policy)
        print("L4-L5: passed")
        print(json.dumps(result, indent=2, default=str))
    except LirixSecurityException as exc:
        print(f"Blocked at simulation: {exc}")
        return
    if repair:
        print("Self-repair closed loop: repaired payload reached L4/L5 successfully.")


def main() -> None:
    config = _build_config()
    client = Lirix(config)
    policy = _policy()

    malicious = {
        "to": MANTLE_MOEROUTER,
        "function_name": "swap",
        "value": 0,
        "data": build_moe_swap_calldata(amount_out_min=0, recipient=PHISHING_RECIPIENT),
    }
    _print_case("Malicious payload", malicious, "Blocked point should be amountOutMin=0 / recipient poisoning.")
    _run(client, malicious, policy)

    repaired = {
        "to": MANTLE_MOEROUTER,
        "function_name": "swap",
        "value": 0,
        "data": build_moe_swap_calldata(amount_out_min=1, recipient=SAFE_RECIPIENT),
    }
    _print_case("Repaired payload", repaired, "Repair evidence: amountOutMin increased; recipient replaced.")
    _run(client, repaired, policy, repair=True)


if __name__ == "__main__":
    main()
