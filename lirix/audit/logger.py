# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Final, Mapping, Optional, Protocol, TextIO, cast

from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_ON_AUDIT_LOG


class SupportsIsolatedHookInvoke(Protocol):
    """Structural type for dispatching audit rows through hooks without importing HookManager."""

    def invoke_hooks_isolated(
        self,
        hook_point: str,
        *args: Any,
        timeout_sec: Optional[float] = None,
        **kwargs: Any,
    ) -> Any: ...


_PK_SUFFIX = re.compile(r"pk$", re.IGNORECASE)
# 键名子串匹配（大小写不敏感）：防止用户 context 中的凭据泄漏到 stdout / hook
_SENSITIVE_KEY_SUBSTRINGS: Final[tuple[str, ...]] = ("key", "secret", "token")


def _key_name_is_sensitive(key: str) -> bool:
    lower = str(key).lower()
    return any(part in lower for part in _SENSITIVE_KEY_SUBSTRINGS)


def _redact_sensitive_tree(obj: Any) -> Any:
    """递归脱敏：键名含 key/secret/token 子串的值替换为 [REDACTED]。"""
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)
            if _key_name_is_sensitive(ks):
                out[ks] = "[REDACTED]"
            else:
                out[ks] = _redact_sensitive_tree(v)
        return out
    if isinstance(obj, list):
        return [_redact_sensitive_tree(x) for x in obj]
    return obj


def _utc_timestamp_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_attributes(data: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in data.items():
        if _PK_SUFFIX.search(str(key)):
            continue
        out[str(key)] = value
    return cast(Dict[str, Any], _redact_sensitive_tree(out))


def _risk_to_severity_text(risk_level: str) -> str:
    normalized = risk_level.strip().lower()
    if normalized in {"critical", "crit"}:
        return "FATAL"
    if normalized in {"high"}:
        return "ERROR"
    if normalized in {"medium", "med"}:
        return "WARN"
    if normalized in {"low"}:
        return "INFO"
    return "INFO"


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    tx_draft_id: str
    intent: str
    blocked_by_layer: str
    risk_level: str
    reason: str
    attributes: Dict[str, Any]
    simulation_result: Optional[str]


class AuditLogger:
    """审计日志：OTel 风格字段 + ISO-8601 UTC（Z），无遥测外发。"""

    def __init__(
        self,
        stream: TextIO = sys.stdout,
        *,
        hook_manager: Optional[SupportsIsolatedHookInvoke] = None,
    ) -> None:
        self._stream = stream
        self._hook_manager = hook_manager

    def emit(
        self,
        *,
        tx_draft_id: str,
        intent: str,
        blocked_by_layer: str,
        risk_level: str,
        reason: str,
        context: Optional[Mapping[str, Any]] = None,
        simulation_result: Optional[str] = None,
    ) -> AuditEvent:
        raw_ctx = dict(context or {})
        attributes = _sanitize_attributes(
            {
                "lirix.tx_draft_id": tx_draft_id,
                "lirix.intent": intent,
                "lirix.blocked_by_layer": blocked_by_layer,
                "lirix.risk_level": risk_level,
                "lirix.reason": reason,
                **raw_ctx,
            }
        )
        event = AuditEvent(
            timestamp=_utc_timestamp_iso_z(),
            tx_draft_id=tx_draft_id,
            intent=intent,
            blocked_by_layer=blocked_by_layer,
            risk_level=risk_level,
            reason=reason,
            attributes=attributes,
            simulation_result=simulation_result,
        )
        severity_text = _risk_to_severity_text(risk_level)
        payload: Dict[str, Any] = {
            "timestamp": event.timestamp,
            "severity_text": severity_text,
            "attributes": event.attributes,
            "body": {
                "message": reason,
                "simulation_result": simulation_result,
            },
        }
        self._stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._stream.flush()
        hm = self._hook_manager
        if hm is not None:
            audit_payload = _redact_sensitive_tree(
                {
                    "timestamp": event.timestamp,
                    "tx_draft_id": event.tx_draft_id,
                    "intent": event.intent,
                    "blocked_by_layer": event.blocked_by_layer,
                    "risk_level": event.risk_level,
                    "reason": event.reason,
                    "attributes": event.attributes,
                    "simulation_result": event.simulation_result,
                }
            )
            hm.invoke_hooks_isolated(
                HOOK_ON_AUDIT_LOG,
                audit_event=audit_payload,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return event

    def emit_system_event(
        self,
        *,
        blocked_by_layer: str,
        risk_level: str,
        reason: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """系统内部事件：只写 stdout，不触发 ``on_audit_log``（避免递归）。"""
        raw = dict(context or {})
        attributes = _sanitize_attributes(
            {
                "lirix.system_event": True,
                "lirix.blocked_by_layer": blocked_by_layer,
                "lirix.risk_level": risk_level,
                "lirix.reason": reason,
                **raw,
            }
        )
        payload: Dict[str, Any] = {
            "timestamp": _utc_timestamp_iso_z(),
            "severity_text": _risk_to_severity_text(risk_level),
            "attributes": attributes,
            "body": {"message": reason},
        }
        self._stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._stream.flush()

    @staticmethod
    def new_tx_draft_id() -> str:
        return str(uuid.uuid4())
