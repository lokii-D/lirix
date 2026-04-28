from __future__ import annotations

import warnings
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

warnings.filterwarnings(
    "ignore",
    message=(
        "websockets\\.legacy is deprecated; see "
        "https://websockets\\.readthedocs\\.io/en/stable/howto/upgrade\\.html "
        "for upgrade instructions"
    ),
    category=DeprecationWarning,
    module="websockets\\.legacy",
)

from web3 import Web3  # noqa: E402


@pytest.fixture  # type: ignore[misc]
def vitalik_lower() -> str:
    return "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"


@pytest.fixture  # type: ignore[misc]
def vitalik_checksum(vitalik_lower: str) -> str:
    return Web3.to_checksum_address(vitalik_lower)


@pytest.fixture  # type: ignore[misc]
def other_checksum() -> str:
    return Web3.to_checksum_address("0x0000000000000000000000000000000000000001")


@pytest.fixture(autouse=True)  # type: ignore[misc]
def mock_async_http_provider_make_request() -> Generator[None, None, None]:
    """Prevent real RPC requests during tests by default."""

    with patch(
        "web3.providers.rpc.AsyncHTTPProvider.make_request", new_callable=AsyncMock
    ) as mocked:
        mocked.return_value = {"jsonrpc": "2.0", "id": 1, "result": None}
        yield
