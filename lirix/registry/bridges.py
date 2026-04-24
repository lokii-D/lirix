from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from web3 import Web3

from lirix.core.exceptions import ValidationFailedException


class BridgeProtocol(str, Enum):
    LAYERZERO = "LayerZero"
    WORMHOLE = "Wormhole"


@dataclass(frozen=True)
class BridgeRoute:
    router_address: str
    function_name: str
    function_signature: str


BRIDGE_REGISTRY: Dict[BridgeProtocol, Dict[int, BridgeRoute]] = {
    BridgeProtocol.LAYERZERO: {
        1: BridgeRoute(
            router_address=Web3.to_checksum_address("0x1111111111111111111111111111111111111111"),
            function_name="send",
            function_signature="send(uint16,bytes,uint256)",
        ),
        42161: BridgeRoute(
            router_address=Web3.to_checksum_address("0x2222222222222222222222222222222222222222"),
            function_name="send",
            function_signature="send(uint16,bytes,uint256)",
        ),
    },
    BridgeProtocol.WORMHOLE: {
        1: BridgeRoute(
            router_address=Web3.to_checksum_address("0x3333333333333333333333333333333333333333"),
            function_name="publishMessage",
            function_signature="publishMessage(uint32,bytes,uint8)",
        ),
    },
}


def resolve_bridge_route(protocol: str, src_chain: int) -> BridgeRoute:
    try:
        protocol_key = BridgeProtocol(protocol)
    except ValueError as exc:
        raise ValidationFailedException(
            error_code="LRX_BRIDGE_PROTOCOL_UNSUPPORTED",
            resolution_agent="Use a supported bridge protocol from the official registry.",
            resolution_dev="Add the protocol to lirix/registry/bridges.py before using it.",
            value_protected="Cross-Chain Intent",
            context={"protocol": protocol},
        ) from exc

    route = BRIDGE_REGISTRY.get(protocol_key, {}).get(int(src_chain))
    if route is None:
        raise ValidationFailedException(
            error_code="LRX_BRIDGE_ROUTE_UNSUPPORTED",
            resolution_agent="Use a source chain available in the bridge registry.",
            resolution_dev="Add the protocol+chain route to lirix/registry/bridges.py.",
            value_protected="Cross-Chain Intent",
            context={"protocol": protocol, "src_chain": src_chain},
        )
    return route
