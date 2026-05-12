from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, cast

from lirix.core.exceptions import ConfigurationGuardException


class DecoderPlugin(Protocol):
    name: str

    def can_handle(self, *, selector: bytes, to_address: str) -> bool: ...

    def decode_and_collect(
        self, *, selector: bytes, body: bytes, payload: Mapping[str, Any]
    ) -> Dict[str, Any]: ...


def _normalize_plugin_name(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationGuardException(
            human_readable_reason="Decoder plugin name must be a non-empty string.",
            context={"reason": "decoder_plugin_name_invalid"},
        )
    name = raw.strip()
    lowered = name.lower()
    if lowered != name:
        # Stable, case-sensitive names avoid ambiguous references across ecosystems.
        raise ConfigurationGuardException(
            human_readable_reason="Decoder plugin name must be lowercase for stability.",
            context={"reason": "decoder_plugin_name_not_lowercase", "name": name},
        )
    if any(ch.isspace() for ch in name):
        raise ConfigurationGuardException(
            human_readable_reason="Decoder plugin name must not contain whitespace.",
            context={"reason": "decoder_plugin_name_whitespace", "name": name},
        )
    return name


def _assert_decoder_plugin_shape(plugin: Any) -> DecoderPlugin:
    if plugin is None:
        raise ConfigurationGuardException(
            human_readable_reason="Decoder plugin must be an object, not None.",
            context={"reason": "decoder_plugin_none"},
        )
    if not hasattr(plugin, "name"):
        raise ConfigurationGuardException(
            human_readable_reason="Decoder plugin must expose a stable 'name' attribute.",
            context={"reason": "decoder_plugin_missing_name"},
        )
    if not hasattr(plugin, "can_handle") or not hasattr(plugin, "decode_and_collect"):
        raise ConfigurationGuardException(
            human_readable_reason=(
                "Decoder plugin must implement can_handle and decode_and_collect."
            ),
            context={
                "reason": "decoder_plugin_missing_methods",
                "name": getattr(plugin, "name", None),
            },
        )
    # Typing: trust Protocol conformance at runtime after attribute checks.
    return cast(DecoderPlugin, plugin)


@dataclass(frozen=True)
class DecoderRegistrySnapshot:
    schema_version: str
    names: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {"schema_version": self.schema_version, "names": list(self.names)}


class DecoderRegistry:
    """
    Governance registry for decoder plugins.

    - Registers plugin objects under stable lowercase names.
    - Resolves profile-declared names into validated plugin objects.
    - Produces a minimal snapshot for evidence/replay closure.
    """

    SCHEMA_VERSION: str = "1.0"

    def __init__(self, *, entries: Optional[Mapping[str, DecoderPlugin]] = None) -> None:
        base: Dict[str, DecoderPlugin] = {}
        if entries:
            for k, v in entries.items():
                name = _normalize_plugin_name(k)
                base[name] = _assert_decoder_plugin_shape(v)
        self._entries: Dict[str, DecoderPlugin] = base

    def register(self, plugin: Any) -> str:
        dp = _assert_decoder_plugin_shape(plugin)
        name = _normalize_plugin_name(getattr(dp, "name", None))
        if name in self._entries:
            raise ConfigurationGuardException(
                human_readable_reason="Duplicate decoder plugin name is not allowed.",
                context={"reason": "decoder_plugin_duplicate", "name": name},
            )
        self._entries[name] = dp
        return name

    def register_all(self, plugins: Iterable[Any]) -> List[str]:
        names: List[str] = []
        for p in plugins:
            names.append(self.register(p))
        return names

    def freeze(self) -> Mapping[str, DecoderPlugin]:
        return MappingProxyType(dict(self._entries))

    def resolve(self, names: Sequence[str], *, strict_mode: bool = True) -> List[DecoderPlugin]:
        out: List[DecoderPlugin] = []
        unknown: List[str] = []
        for raw in names:
            if not isinstance(raw, str) or not raw.strip():
                continue
            key = raw.strip()
            plugin = self._entries.get(key)
            if plugin is None:
                unknown.append(key)
                continue
            out.append(plugin)
        if unknown and strict_mode:
            raise ConfigurationGuardException(
                human_readable_reason="Unknown decoder plugin referenced by chain profile.",
                context={"reason": "decoder_plugin_unknown", "unknown": sorted(set(unknown))},
            )
        return out

    def snapshot(self) -> DecoderRegistrySnapshot:
        return DecoderRegistrySnapshot(
            schema_version=self.SCHEMA_VERSION,
            names=sorted(self._entries.keys()),
        )
