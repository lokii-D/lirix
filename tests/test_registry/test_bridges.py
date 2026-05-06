# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import pytest
from lirix.core.exceptions import ValidationFailedException
from lirix.registry.bridges import BridgeProtocol, resolve_bridge_route


def test_test_bridges() -> None:
    assert resolve_bridge_route(BridgeProtocol.LAYERZERO.value, 1).function_name == "send"
    assert resolve_bridge_route(BridgeProtocol.WORMHOLE.value, 1).router_address.startswith("0x")


def test_test_bridges_2() -> None:
    with pytest.raises(ValidationFailedException, match="LRX_BRIDGE_PROTOCOL_UNSUPPORTED"):
        resolve_bridge_route("bad", 1)
    with pytest.raises(ValidationFailedException, match="LRX_BRIDGE_ROUTE_UNSUPPORTED"):
        resolve_bridge_route(BridgeProtocol.LAYERZERO.value, 999999)
