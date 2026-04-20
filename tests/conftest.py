from __future__ import annotations

import pytest
from web3 import Web3


@pytest.fixture(scope="session")
def vitalik_checksum() -> str:
    return Web3.to_checksum_address("0xd8da6bf26964af9d7eed9e03e53415dedaa90093")


@pytest.fixture()
def vitalik_lower(vitalik_checksum: str) -> str:
    return vitalik_checksum.lower()


@pytest.fixture(scope="session")
def other_checksum() -> str:
    return Web3.to_checksum_address("0x0000000000000000000000000000000000000001")
