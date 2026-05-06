from __future__ import annotations

import lirix.intents.translator as translator
import pytest
from lirix.core.exceptions import ValidationFailedException


class _Route:
    def __init__(self, signature: str) -> None:
        self.function_signature = signature
        self.function_name = "bridge"
        self.router_address = "0x0000000000000000000000000000000000000001"


def test_translate_intent_rejects_unsupported_intent_type() -> None:
    with pytest.raises(ValidationFailedException, match="LRX_INTENT_TYPE_UNSUPPORTED"):
        translator.translate_intent({"type": "swap"})


def test_translate_intent_rejects_bridge_intent_with_missing_fields() -> None:
    with pytest.raises(ValidationFailedException, match="LRX_INTENT_MISSING_FIELDS"):
        translator.translate_intent({"type": "bridge", "protocol": "foo", "src_chain": 1})


def test_translate_intent_rejects_unsupported_bridge_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        translator,
        "resolve_bridge_route",
        lambda protocol, src_chain: _Route("f(uint256,uint256,uint256,uint256)"),
    )
    with pytest.raises(ValidationFailedException, match="LRX_BRIDGE_SIGNATURE_UNSUPPORTED"):
        translator.translate_intent(
            {"type": "bridge", "protocol": "foo", "src_chain": 1, "dst_chain": 2, "amount": 3}
        )
