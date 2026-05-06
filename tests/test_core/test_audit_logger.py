# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import json
from io import StringIO

from lirix.audit.logger import AuditLogger
from lirix.core.constants import HOOK_ON_AUDIT_LOG
from lirix.core.hook_manager import HookManager


def test_audit_logger_maps_risk_levels_to_severity_text() -> None:
    buf = StringIO()
    log = AuditLogger(stream=buf)
    for risk, expected in (
        ("critical", "FATAL"),
        ("crit", "FATAL"),
        ("high", "ERROR"),
        ("medium", "WARN"),
        ("med", "WARN"),
        ("low", "INFO"),
        ("unknown", "INFO"),
    ):
        buf.truncate(0)
        buf.seek(0)
        log.emit(
            tx_draft_id="t",
            intent="i",
            blocked_by_layer="L1",
            risk_level=risk,
            reason="r",
        )
        payload = json.loads(buf.getvalue().strip())
        assert payload["severity_text"] == expected


def test_audit_logger_redacts_nested_refresh_tokens() -> None:
    buf = StringIO()
    log = AuditLogger(stream=buf)
    log.emit(
        tx_draft_id="t",
        intent="i",
        blocked_by_layer="L1",
        risk_level="low",
        reason="r",
        context={"items": [{"refresh_token": "rt"}]},
    )
    payload = json.loads(buf.getvalue().strip())
    assert payload["attributes"]["items"][0]["refresh_token"] == "[REDACTED]"


def test_audit_logger_redacts_api_and_oauth_secrets() -> None:
    buf = StringIO()
    log = AuditLogger(stream=buf)
    log.emit(
        tx_draft_id="t",
        intent="i",
        blocked_by_layer="L1",
        risk_level="low",
        reason="r",
        context={"api_key": "sk-12345", "nested": {"oauth_token": "t"}, "safe": 1},
    )
    payload = json.loads(buf.getvalue().strip())
    attrs = payload["attributes"]
    assert attrs["safe"] == 1
    assert attrs["api_key"] == "[REDACTED]"
    assert attrs["nested"]["oauth_token"] == "[REDACTED]"
    assert "sk-12345" not in buf.getvalue()


def test_audit_logger_emits_redacted_hook_attributes() -> None:
    buf = StringIO()
    mgr = HookManager()
    captured: list[dict[str, object]] = []

    def on_audit(*args: object, **kwargs: object) -> None:
        ev = kwargs.get("audit_event")
        if isinstance(ev, dict) and isinstance(ev.get("attributes"), dict):
            captured.append(dict(ev["attributes"]))

    mgr.register_hook(HOOK_ON_AUDIT_LOG, on_audit)
    log = AuditLogger(stream=buf, hook_manager=mgr)
    log.emit(
        tx_draft_id="x",
        intent="swap",
        blocked_by_layer="core",
        risk_level="low",
        reason="ok",
        context={"api_key": "sk-secret"},
    )
    assert captured
    assert captured[0].get("api_key") == "[REDACTED]"


def test_audit_logger_passes_audit_event_to_hook_manager() -> None:
    buf = StringIO()
    mgr = HookManager()
    seen: list[dict[str, object]] = []

    def on_audit(*args: object, **kwargs: object) -> None:
        ev = kwargs.get("audit_event")
        if isinstance(ev, dict):
            seen.append(ev)

    mgr.register_hook(HOOK_ON_AUDIT_LOG, on_audit)
    log = AuditLogger(stream=buf, hook_manager=mgr)
    log.emit(
        tx_draft_id="tid",
        intent="swap",
        blocked_by_layer="L3",
        risk_level="low",
        reason="ok",
    )
    assert seen and seen[0].get("intent") == "swap"


def test_audit_logger_redacts_private_key_like_fields() -> None:
    buf = StringIO()
    log = AuditLogger(stream=buf)
    log.emit(
        tx_draft_id="t1",
        intent="i",
        blocked_by_layer="core",
        risk_level="high",
        reason="r",
        context={"safe": 1, "user_pk": "hidden"},
    )
    payload = json.loads(buf.getvalue().strip())
    attrs = payload["attributes"]
    assert attrs["safe"] == 1
    assert "user_pk" not in attrs
    assert "treasury_pk" not in attrs
