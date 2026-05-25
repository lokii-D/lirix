import pytest
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import RPCUnavailableException, SchemaValidationException
from lirix.core.failure_protocol import FAILURE_PROTOCOL_SCHEMA_VERSION


def test_mantle_orchestrator_full_pipeline() -> None:
    config = LirixConfig.for_mantle(strict_mode=True)
    lx = Lirix(config)
    malicious = {
        "to": "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
        "function_name": "swap",
        "data": "0x1234",
        "value": 0,
    }
    with pytest.raises((SchemaValidationException, RPCUnavailableException)) as exc:
        lx.validate_and_simulate("swap", malicious)
    payload = exc.value.args[0] if exc.value.args else str(exc.value)
    assert "canonical_error_code" in payload
    assert isinstance(payload, str)
    assert FAILURE_PROTOCOL_SCHEMA_VERSION in str(payload) or "LRX_LEGACY_ERROR" in str(payload)
