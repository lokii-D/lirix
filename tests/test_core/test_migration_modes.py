from __future__ import annotations

import pytest
from lirix import Lirix
from lirix.core.config import LirixConfig


def test_validate_only_returns_migration_modes_metadata() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        hook_contract_mode="warn",
        policy_lifecycle_mode="digest_verified",
        rpc_evidence_mode="v2_only",
    )
    client = Lirix(cfg)
    result = client.validate_only(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": "0x",
            "value": 0,
        },
    )
    assert "migration_modes" in result
    assert result["migration_modes"]["hook_contract_mode"] == "warn"
    assert result["migration_modes"]["policy_lifecycle_mode_effective"] == "digest_verified"


@pytest.mark.filterwarnings(
    "ignore:policy_lifecycle_mode=signed_only is deprecated:DeprecationWarning"
)
def test_signed_only_maps_to_effective_digest_verified() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        whitelisted_addresses=["0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"],
        hook_contract_mode="warn",
        policy_lifecycle_mode="signed_only",
        rpc_evidence_mode="v2_only",
    )
    client = Lirix(cfg)
    result = client.validate_only(
        "swap",
        {
            "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "function_name": "swapExactTokensForTokens",
            "data": "0x",
            "value": 0,
        },
    )
    assert result["migration_modes"]["policy_lifecycle_mode"] == "digest_verified"
    assert result["migration_modes"]["policy_lifecycle_mode_effective"] == "digest_verified"
