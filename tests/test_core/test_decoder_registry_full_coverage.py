"""Branch-complete coverage for lirix.core.decoder_registry (governance paths)."""

from __future__ import annotations

import pytest
from lirix.core.decoder_registry import (
    DecoderRegistry,
    DecoderRegistrySnapshot,
)
from lirix.core.exceptions import ConfigurationGuardException


class _Plugin:
    name = "alpha"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return True

    def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
        return {}


class _PluginUpperName:
    name = "Beta"

    def can_handle(self, *, selector: bytes, to_address: str) -> bool:
        return False

    def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
        return {}


def test_normalize_rejects_empty_plugin_name_on_register() -> None:
    reg = DecoderRegistry()
    bad = _Plugin()
    bad.name = "   "
    with pytest.raises(ConfigurationGuardException):
        reg.register(bad)


def test_normalize_rejects_uppercase_name() -> None:
    reg = DecoderRegistry()
    with pytest.raises(ConfigurationGuardException):
        reg.register(_PluginUpperName())


def test_normalize_rejects_whitespace_in_name() -> None:
    reg = DecoderRegistry()
    p = _Plugin()
    p.name = "bad name"
    with pytest.raises(ConfigurationGuardException):
        reg.register(p)


def test_register_rejects_none_plugin() -> None:
    reg = DecoderRegistry()
    with pytest.raises(ConfigurationGuardException):
        reg.register(None)


def test_register_rejects_missing_name_attr() -> None:
    reg = DecoderRegistry()

    class NoName:
        def can_handle(self, *, selector: bytes, to_address: str) -> bool:
            return True

        def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
            return {}

    with pytest.raises(ConfigurationGuardException):
        reg.register(NoName())


def test_register_rejects_missing_methods() -> None:
    reg = DecoderRegistry()

    class Bad:
        name = "x"

    with pytest.raises(ConfigurationGuardException) as exc:
        reg.register(Bad())
    assert exc.value.context.get("reason") == "decoder_plugin_missing_methods"


def test_register_duplicate_rejected() -> None:
    reg = DecoderRegistry()
    reg.register(_Plugin())
    with pytest.raises(ConfigurationGuardException) as exc:
        reg.register(_Plugin())
    assert exc.value.context.get("reason") == "decoder_plugin_duplicate"


def test_registry_init_with_entries_mapping() -> None:
    p = _Plugin()
    reg = DecoderRegistry(entries={"alpha": p})
    assert reg.resolve(["alpha"], strict_mode=True) == [p]


def test_registry_init_normalizes_entry_keys() -> None:
    p = _Plugin()
    reg = DecoderRegistry(entries={" alpha ": p})
    assert reg.snapshot().names == ["alpha"]


def test_register_all_and_freeze() -> None:
    reg = DecoderRegistry()
    names = reg.register_all([_Plugin()])
    assert names == ["alpha"]
    frozen = reg.freeze()
    assert "alpha" in frozen
    assert len(frozen) == 1


def test_resolve_skips_blank_strings_and_non_strict_unknown() -> None:
    reg = DecoderRegistry()
    reg.register(_Plugin())
    out = reg.resolve(["alpha", "   ", "missing"], strict_mode=False)
    assert [p.name for p in out] == ["alpha"]


def test_resolve_strict_unknown_raises() -> None:
    reg = DecoderRegistry()
    reg.register(_Plugin())
    with pytest.raises(ConfigurationGuardException) as exc:
        reg.resolve(["nope"], strict_mode=True)
    assert exc.value.context.get("reason") == "decoder_plugin_unknown"


def test_snapshot_to_dict() -> None:
    snap = DecoderRegistrySnapshot(schema_version="1.0", names=["a", "b"])
    d = snap.to_dict()
    assert d == {"schema_version": "1.0", "names": ["a", "b"]}


def test_init_rejects_bad_dict_key() -> None:
    with pytest.raises(ConfigurationGuardException):
        DecoderRegistry(entries={"": _Plugin()})


def test_init_rejects_bad_plugin_in_entries() -> None:
    with pytest.raises(ConfigurationGuardException):
        DecoderRegistry(entries={"x": object()})
