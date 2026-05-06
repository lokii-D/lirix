# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import builtins

import pytest
from lirix.core.builder import CalldataBuilder, LirixTxBuilder


def test_test_builder_builder_normalize_draft_path() -> None:
    tx = LirixTxBuilder()
    tx._draft_payload = {"data": "0XABCD"}  # noqa: SLF001
    tx.assert_erc20_balance_increase("0x0000000000000000000000000000000000000001", 3)
    out = tx.build()
    assert out["data"] == "0xABCD"
    assert out["assertions"][0]["expected_value"] == 3


def test_test_builder_builder_normalize_draft_path_2(monkeypatch: pytest.MonkeyPatch) -> None:
    b = CalldataBuilder()
    monkeypatch.setattr(
        b,
        "_load_deps",
        lambda: (lambda *_: (_ for _ in ()).throw(RuntimeError("boom")), __import__("web3").Web3),
    )
    with pytest.raises(Exception, match="LRX_VALIDATION_ABI_ENCODE"):
        b.build("ping()", [])


def test_test_builder_builder_normalize_draft_path_3(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "eth_abi":
            raise ImportError("missing eth_abi")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(Exception, match="LRX_DEP_SIMULATION_MISSING"):
        CalldataBuilder()._load_deps()  # noqa: SLF001


def test_test_builder_builder_normalize_draft_path_4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(CalldataBuilder, "build", lambda self, sig, args: "0x1234")
    built = LirixTxBuilder("ping()", []).build()
    assert built == {"data": "0x1234"}
