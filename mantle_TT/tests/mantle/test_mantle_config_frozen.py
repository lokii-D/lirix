import pytest
from lirix import LirixConfig
from pydantic import ValidationError


def test_mantle_config_frozen_and_preset() -> None:
    config = LirixConfig.for_mantle()
    assert config.chain_id in (5000, 5001)
    assert len(config.rpc_urls) >= 3
    assert config.multicall3_address == "0xcA11bde05977b3631167028862bE2a173976CA11"
    with pytest.raises(ValidationError):
        config.extra_field = "fail"
