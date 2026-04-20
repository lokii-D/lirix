# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Mapping, Optional

from web3 import Web3

from lirix.core.config import LirixConfig
from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L1
from lirix.core.exceptions import InvalidIntentException
from lirix.core.hook_manager import HookManager
from lirix.core.signatures import INTENT_TO_ALLOWED_SELECTORS


class IntentValidator:
    """L1：意图、外层目标白名单与 calldata Method ID 对账，阻断提示词注入与语义欺骗。"""

    def __init__(self, config: LirixConfig, *, hooks: Optional[HookManager] = None) -> None:
        self._config = config
        self._hooks = hooks

    @staticmethod
    def _extract_method_id(payload: dict[str, Any]) -> Optional[bytes]:
        raw = payload.get("data", "0x")
        if not isinstance(raw, str) or raw == "0x":
            return None
        if len(raw) < 10:
            return None
        try:
            blob = bytes.fromhex(raw[2:])
        except ValueError as exc:
            raise InvalidIntentException(
                human_readable_reason=(
                    "data is not valid hex; cannot reconcile intent with method id."
                ),
                context={"layer": "L1"},
            ) from exc
        return blob[:4]

    def _reconcile_intent_with_method_id(self, intent: str, payload: dict[str, Any]) -> None:
        allowed = INTENT_TO_ALLOWED_SELECTORS.get(intent)
        if allowed is None:
            return
        sel = self._extract_method_id(payload)
        if sel is None:
            return
        if sel not in allowed:
            raise InvalidIntentException(
                human_readable_reason=(
                    "Declared intent does not match calldata method id (semantic mismatch)."
                ),
                context={
                    "layer": "L1",
                    "intent": intent,
                    "selector": f"0x{sel.hex()}",
                },
            )

    def validate(self, intent: str, payload: dict[str, Any]) -> bool:
        if not self._config.allowed_intents:
            raise InvalidIntentException(
                human_readable_reason="allowed_intents is empty; fail-closed.",
                context={"layer": "L1", "field": "allowed_intents"},
            )
        if intent not in self._config.allowed_intents:
            raise InvalidIntentException(
                human_readable_reason="Intent is not in allowed_intents.",
                context={"layer": "L1", "intent": intent},
            )
        if not self._config.allowed_function_names:
            raise InvalidIntentException(
                human_readable_reason="allowed_function_names is empty; fail-closed.",
                context={"layer": "L1", "field": "allowed_function_names"},
            )
        if not self._config.allowed_to_addresses:
            raise InvalidIntentException(
                human_readable_reason="allowed_to_addresses is empty; fail-closed.",
                context={"layer": "L1", "field": "allowed_to_addresses"},
            )
        try:
            fn = payload["function_name"]
            raw_to = payload["to"]
        except KeyError as exc:
            raise InvalidIntentException(
                human_readable_reason="Payload missing function_name or to.",
                context={"layer": "L1", "missing": exc.args[0]},
            ) from exc
        if not isinstance(fn, str) or not fn.strip():
            raise InvalidIntentException(
                human_readable_reason="function_name must be a non-empty string.",
                context={"layer": "L1", "function_name": fn},
            )
        if fn.strip() not in self._config.allowed_function_names:
            raise InvalidIntentException(
                human_readable_reason="function_name is not allow-listed.",
                context={"layer": "L1", "function_name": fn},
            )
        if not isinstance(raw_to, str) or not Web3.is_address(raw_to.strip()):
            raise InvalidIntentException(
                human_readable_reason="to must be a valid hex address.",
                context={"layer": "L1", "to": raw_to},
            )
        to_cs = Web3.to_checksum_address(raw_to.strip())
        if to_cs not in self._config.allowed_to_addresses:
            raise InvalidIntentException(
                human_readable_reason="to is not in allowed_to_addresses.",
                context={"layer": "L1", "to": to_cs},
            )
        self._reconcile_intent_with_method_id(intent, payload)
        h = self._hooks
        if h is not None:
            h.invoke_hooks_isolated(
                HOOK_LAYER_L1,
                layer="L1",
                intent=intent,
                payload=payload,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return True

    def validate_mapping(self, intent: str, payload: Mapping[str, Any]) -> bool:
        return self.validate(intent, dict(payload))
