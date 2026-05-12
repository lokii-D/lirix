# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_copy_inspection_result_preserves_empty_result() -> None:
    copied = ProxyPiercer._copy_inspection_result({})
    assert copied == {}


def test_copy_inspection_result_keeps_non_resolution_path_fields() -> None:
    result = {"resolution_path": ("a", "b"), "admin": "0x1", "nested": {"x": 1}}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["admin"] == "0x1"
    assert copied["nested"] == {"x": 1}


def test_copy_inspection_result_missing_resolution_path_passthrough() -> None:
    res = {"x": 1}
    copied = ProxyPiercer._copy_inspection_result(res)
    assert copied == res


def test_copy_inspection_result_allows_plain_dicts() -> None:
    result = {"a": 1, "b": {"c": 2}}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied == result


def test_copy_inspection_result_nested_dict_passthrough() -> None:
    result = {"resolution_path": ["eip1967"], "nested": {"a": 1}, "x": 1}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["nested"] == {"a": 1}
    assert copied["resolution_path"] == ["eip1967"]


def test_copy_inspection_result_nested_resolution_path_list_passthrough() -> None:
    res = {"resolution_path": [["a"]], "x": 1}
    copied = ProxyPiercer._copy_inspection_result(res)
    assert copied["resolution_path"] == [["a"]]


def test_copy_inspection_result_resolution_path_conversion_only() -> None:
    result = {"resolution_path": ("eip1967", "fallback"), "x": 1}
    copied = ProxyPiercer._copy_inspection_result(result)
    assert copied["resolution_path"] == ["eip1967", "fallback"]
    assert copied["x"] == 1
