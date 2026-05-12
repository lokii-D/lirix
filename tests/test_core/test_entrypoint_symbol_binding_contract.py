from __future__ import annotations

import importlib
from typing import Mapping

import lirix
import pytest


def test_top_level_resolve_failure_protocol_symbol_is_callable_and_stable() -> None:
    assert "resolve_failure_protocol" in lirix.__all__
    assert callable(lirix.resolve_failure_protocol)


def test_lirix_core_guard_module_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("lirix.core.guard")


def test_top_level_resolve_failure_protocol_delegates_to_classmethod() -> None:
    payload: Mapping[str, object] = {
        "failure_protocol": {
            "failure_layer": "L1",
            "failure_type": "timeout",
            "retryable": True,
            "repair_hint": "retry",
            "details": {"context": {"reason": "timeout"}},
        }
    }
    a = lirix.resolve_failure_protocol(payload)
    b = lirix.Lirix.resolve_failure_protocol(payload)
    assert dict(a) == dict(b)
