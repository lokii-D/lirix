from __future__ import annotations

import pytest
from lirix.core.config import LirixConfig
from lirix.core.exceptions import MaliciousPayloadException
from lirix.core.signatures import EXACT_INPUT_SELECTOR
from lirix.layers.l3_defi_parser import DeFiPayloadParser


def _cfg() -> LirixConfig:
    return LirixConfig(chain_id=1, rpc_urls=[], allowed_intents=["swap"])


def test_test_l3_defi_parser_collect_v3_path_rejects_too_short_path() -> None:
    parser = DeFiPayloadParser(_cfg())
    short_path = bytes.fromhex("11" * 19)
    with pytest.raises(MaliciousPayloadException, match="too short"):
        parser._collect_v3_path_addresses(
            short_path, set(), selector=EXACT_INPUT_SELECTOR
        )  # noqa: SLF001


def test_test_l3_defi_parser_collect_v3_path_rejects_too_short_path_2() -> None:
    parser = DeFiPayloadParser(_cfg())
    # 20-byte token + only 2 bytes fee => malformed layout
    broken_path = bytes.fromhex("11" * 20 + "aabb")
    with pytest.raises(MaliciousPayloadException, match="malformed"):
        parser._collect_v3_path_addresses(
            broken_path, set(), selector=EXACT_INPUT_SELECTOR
        )  # noqa: SLF001
