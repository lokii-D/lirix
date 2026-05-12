from __future__ import annotations

from typing import Any

import pytest
from lirix import Lirix, LirixConfig
from lirix.core import HookExecutionException
from lirix.core.exceptions import RPCUnavailableException
from lirix.core.multicall import MulticallEncoder
from web3 import Web3


def _build_local_guardian(w3: Web3) -> Lirix:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    recipient = w3.eth.accounts[0]
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=["http://127.0.0.1:8545"],
        allowed_intents=["swap"],
        allowed_function_names=["aggregate3"],
        allowed_to_addresses=[mc, recipient],
        whitelisted_addresses=sorted({mc, recipient}),
        blacklisted_addresses=[],
    )
    return Lirix(cfg)


def _multicall_payload(w3: Web3) -> dict[str, Any]:
    mc = Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    recipient = w3.eth.accounts[0]
    encoded = MulticallEncoder(mc).encode_transactions([{"to": recipient, "data": "0x"}])
    return {
        "to": encoded["to"],
        "function_name": "aggregate3",
        "data": encoded["data"],
        "value": encoded.get("value", 0),
    }


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.slow
def test_real_e2e_mainline_validate_and_simulate(deploy_multicall3_locally: Web3) -> None:
    guard = _build_local_guardian(deploy_multicall3_locally)
    try:
        out = guard.validate_and_simulate("swap", _multicall_payload(deploy_multicall3_locally))
    except RPCUnavailableException:
        pytest.skip("Local RPC quorum unavailable for Lirix integration scenario.")
    assert out["decision"] == "approved"
    assert out["payload"]["simulation_ok"] is True


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.slow
def test_real_e2e_blocked_path_by_hook(deploy_multicall3_locally: Web3) -> None:
    guard = _build_local_guardian(deploy_multicall3_locally)

    def _blocked_invoke(*args: object, **kwargs: object) -> list[dict[str, object]]:
        _ = (args, kwargs)
        return [{"ok": False, "failure_level": "fatal", "reason": "human_review_required"}]

    guard.hooks.invoke_hooks_isolated = _blocked_invoke  # type: ignore[assignment]
    with pytest.raises(HookExecutionException, match="rejected payload"):
        guard.validate_and_simulate("swap", _multicall_payload(deploy_multicall3_locally))


@pytest.mark.e2e
@pytest.mark.network
@pytest.mark.slow
def test_real_e2e_retry_after_fix_path(deploy_multicall3_locally: Web3) -> None:
    guard = _build_local_guardian(deploy_multicall3_locally)
    bad_payload = dict(_multicall_payload(deploy_multicall3_locally))
    bad_payload["to"] = Web3.to_checksum_address("0x000000000000000000000000000000000000dEaD")

    try:
        guard.validate_and_simulate("swap", bad_payload)
    except RPCUnavailableException:
        pytest.skip("Local RPC quorum unavailable for Lirix integration scenario.")
    except Exception:
        pass
    else:
        pytest.fail("expected first swap attempt to raise")

    fixed = _multicall_payload(deploy_multicall3_locally)
    try:
        out = guard.validate_and_simulate("swap", fixed)
    except RPCUnavailableException:
        pytest.skip("Local RPC quorum unavailable for Lirix integration scenario.")
    assert out["decision"] == "approved"
    assert out["payload"]["simulation_ok"] is True
