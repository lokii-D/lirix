from __future__ import annotations

from typing import Any, Dict, Mapping

from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_LAYER_L3
from lirix.core.hook_manager import HookManager
from lirix.layers.l3_defi_parser import DeFiPayloadParser


class _Plugin:
    name = "test-plugin"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return selector == b"\x12\x34\x56\x78"

    def decode_and_collect(
        self, *, selector: bytes, body: bytes, payload: Mapping[str, Any]
    ) -> Dict[str, Any]:
        return {"ok": True}


class _NoopPlugin:
    name = "noop"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return False

    def decode_and_collect(
        self, *, selector: bytes, body: bytes, payload: Mapping[str, Any]
    ) -> Dict[str, Any]:
        return {"ok": False}


def test_l3_decoder_plugin_short_circuits_and_invokes_hook() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        decoder_plugins=[_NoopPlugin(), _Plugin()],
    )
    mgr = HookManager()
    called: dict[str, int] = {"n": 0}

    def hook(*args: object, **kwargs: object) -> None:
        called["n"] += 1

    mgr.register_hook(HOOK_LAYER_L3, hook)
    parser = DeFiPayloadParser(cfg, hooks=mgr)
    payload = {"to": "0x0000000000000000000000000000000000000001", "data": "0x12345678"}
    assert parser.validate(payload) is True
    assert called["n"] == 1


def test_l3_decoder_plugin_short_circuits_without_hooks() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=False,
        rpc_urls=[],
        decoder_plugins=[_Plugin()],
    )
    parser = DeFiPayloadParser(cfg, hooks=None)
    payload = {"to": "0x0000000000000000000000000000000000000001", "data": "0x12345678"}
    assert parser.validate(payload) is True
