from __future__ import annotations

from typing import Any, Dict

from lirix.core.builder import CalldataBuilder
from lirix.core.exceptions import ValidationFailedException
from lirix.registry.bridges import resolve_bridge_route


def translate_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    intent_type = intent.get("type")
    if intent_type != "bridge":
        raise ValidationFailedException(
            error_code="LRX_INTENT_TYPE_UNSUPPORTED",
            resolution_agent="Use a supported high-level intent type.",
            resolution_dev="Only bridge intent is currently supported by the translator.",
            value_protected="Cross-Chain Intent",
            context={"type": intent_type},
        )
    protocol = str(intent.get("protocol", ""))
    src_chain_raw = intent.get("src_chain")
    dst_chain_raw = intent.get("dst_chain")
    amount_raw = intent.get("amount")
    if src_chain_raw is None or dst_chain_raw is None or amount_raw is None:
        raise ValidationFailedException(
            error_code="LRX_INTENT_MISSING_FIELDS",
            resolution_agent="Provide src_chain, dst_chain, and amount for bridge intent.",
            resolution_dev="Validate bridge intent fields before translation.",
            value_protected="Cross-Chain Intent",
            context={"intent": intent},
        )
    src_chain = int(src_chain_raw)
    dst_chain = int(dst_chain_raw)
    amount = int(amount_raw)

    route = resolve_bridge_route(protocol, src_chain)

    # Minimal deterministic payload shape; arguments are derived from the route signature.
    sig_inputs = route.function_signature.split("(", 1)[1].rstrip(")")
    arity = 0 if not sig_inputs else len([x for x in sig_inputs.split(",") if x.strip()])
    args_by_arity: Dict[int, list[Any]] = {
        1: [amount],
        2: [dst_chain, amount],
        3: [dst_chain, b"", amount],
    }
    if arity not in args_by_arity:
        raise ValidationFailedException(
            error_code="LRX_BRIDGE_SIGNATURE_UNSUPPORTED",
            resolution_agent="Use a bridge route with a supported ABI signature.",
            resolution_dev="Keep bridge signatures to a supported argument shape for translator.",
            value_protected="Cross-Chain Intent",
            context={"function_signature": route.function_signature, "arity": arity},
        )
    data = CalldataBuilder().build(route.function_signature, args_by_arity[arity])
    return {
        "to": route.router_address,
        "function_name": route.function_name,
        "data": data,
    }
