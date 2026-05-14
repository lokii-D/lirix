from __future__ import annotations

from pathlib import Path

import pytest
from lirix import Lirix
from lirix.core.constants import LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT
from lirix.core.exceptions import LirixSecurityException


def _readme_text() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "README.md").read_text(encoding="utf-8")


def test_readme_python_blocks_avoid_legacy_top_level_tx_keys() -> None:
    """README must not regress to result[\"to\"] / result[\"data\"] for validate_and_simulate envelopes."""
    text = _readme_text()
    assert 'result["to"]' not in text
    assert 'result["data"]' not in text


def test_readme_documents_canonical_tx_and_simulation_paths() -> None:
    text = _readme_text()
    assert "Lirix.extract_broadcast_fields(result)" in text
    assert 'result["payload"]' in text
    assert "simulation_ok" in text


def test_extract_broadcast_fields_reads_payload() -> None:
    out = Lirix.extract_broadcast_fields(
        {
            "payload": {"to": "0xabc", "data": "0x01", "value": 2},
            "decision": "approved",
            "status": "approved",
        }
    )
    assert out == {"to": "0xabc", "data": "0x01", "value": 2}


def test_extract_broadcast_fields_value_coerces_invalid_to_zero() -> None:
    assert Lirix.extract_broadcast_fields(
        {
            "payload": {"to": "0xabc", "data": "0x01", "value": "not_an_int"},
            "decision": "approved",
            "status": "approved",
        }
    ) == {"to": "0xabc", "data": "0x01", "value": 0}

    assert Lirix.extract_broadcast_fields(
        {
            "payload": {"to": "0xabc", "data": "0x01", "value": object()},
            "decision": "approved",
            "status": "approved",
        }
    ) == {"to": "0xabc", "data": "0x01", "value": 0}


def test_extract_broadcast_fields_approved_missing_broadcast_raises() -> None:
    with pytest.raises(LirixSecurityException) as excinfo:
        Lirix.extract_broadcast_fields(
            {
                "decision": "approved",
                "status": "approved",
                "payload": {"value": 0},
            }
        )
    exc = excinfo.value
    assert exc.context.get("reason") == "approved_broadcast_fields_invariant"
    assert exc.context.get("canonical_error_code") == LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT
    assert exc.canonical_error_code == LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT


def test_extract_broadcast_fields_approved_non_int_value_coerces_to_zero() -> None:
    """Value coercion must not break the approved-path invariant checks."""
    out = Lirix.extract_broadcast_fields(
        {
            "decision": "approved",
            "status": "approved",
            "payload": {"to": "0xabc", "data": "0x01", "value": "not-an-int"},
        }
    )
    assert out == {"to": "0xabc", "data": "0x01", "value": 0}


def test_extract_broadcast_fields_approved_empty_to_raises() -> None:
    with pytest.raises(LirixSecurityException):
        Lirix.extract_broadcast_fields(
            {
                "decision": "approved",
                "status": "approved",
                "payload": {"to": "", "data": "0x01"},
            }
        )


def test_extract_broadcast_fields_decision_approved_without_status_raises() -> None:
    """Both ``decision`` and ``status`` must be ``approved`` to extract broadcast fields."""
    with pytest.raises(LirixSecurityException) as excinfo:
        Lirix.extract_broadcast_fields(
            {
                "decision": "approved",
                "status": "pending",
                "payload": {},
            }
        )
    assert excinfo.value.context.get("reason") == "broadcast_extract_requires_dual_approved"


def test_extract_broadcast_fields_non_approved_raises() -> None:
    with pytest.raises(LirixSecurityException) as excinfo:
        Lirix.extract_broadcast_fields({"decision": "blocked"})
    assert excinfo.value.context.get("reason") == "broadcast_extract_requires_dual_approved"


def test_extract_broadcast_fields_approved_data_must_be_0x_prefixed_hex() -> None:
    base = {
        "decision": "approved",
        "status": "approved",
        "payload": {"to": "0x0000000000000000000000000000000000000001", "data": "deadbeef"},
    }
    with pytest.raises(LirixSecurityException) as excinfo:
        Lirix.extract_broadcast_fields(base)
    assert "0x-prefixed" in (excinfo.value.human_readable_reason or "")

    # Body after ``0x`` must be an even nibble count; ``0f`` is two nibbles (valid).
    base["payload"]["data"] = "0xf"
    with pytest.raises(LirixSecurityException) as excinfo2:
        Lirix.extract_broadcast_fields(base)
    assert "even" in (excinfo2.value.human_readable_reason or "").lower()

    base["payload"]["data"] = "0x0g"
    with pytest.raises(LirixSecurityException) as excinfo3:
        Lirix.extract_broadcast_fields(base)
    assert "invalid hexadecimal" in (excinfo3.value.human_readable_reason or "").lower()


def test_readme_real_e2e_docstring_mentions_integration_suite() -> None:
    """Keep README 5-minute flow aligned with tests/test_integration/test_real_e2e_paths.py."""
    text = _readme_text()
    assert "test_real_e2e_paths.py" in text
    assert "simulation_ok" in text and "payload" in text
