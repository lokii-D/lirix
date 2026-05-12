from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from lirix.core.decoder_registry import DecoderPlugin, DecoderRegistry
from lirix.core.exceptions import ConfigurationGuardException

_RPC_POLICY_KNOWN_KEYS: frozenset[str] = frozenset({"request_timeout", "timeout"})


def _partition_rpc_policy(raw: Mapping[str, Any] | None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Keep only allowlisted rpc_policy keys; stash the rest under profile metadata (additive)."""

    accepted: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for k, v in dict(raw or {}).items():
        key = str(k)
        if key in _RPC_POLICY_KNOWN_KEYS:
            accepted[key] = v
        else:
            extra[key] = v
    return accepted, extra


@dataclass(frozen=True)
class ChainProfile:
    chain_id: int
    profile_name: str = "default_profile"
    registry_version: Optional[str] = None
    registry_source: Optional[str] = None
    multicall3_address: Optional[str] = None
    uniswap_v2_router: Optional[str] = None
    rpc_policy: Dict[str, Any] = field(default_factory=dict)
    protocol_registry: Dict[str, str] = field(default_factory=dict)
    address_registry: Dict[str, str] = field(default_factory=dict)
    decoder_plugins: List[str] = field(default_factory=list)
    simulation_backend_profile: Dict[str, Any] = field(default_factory=dict)
    chain_constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    decoder_policy: str = "explicit_only"


@dataclass(frozen=True)
class ProtocolRegistry:
    entries: Dict[str, str] = field(default_factory=dict)
    version: Optional[str] = None
    source: Optional[str] = None

    def resolve(self, protocol: str) -> Optional[str]:
        return self.entries.get(protocol.strip().lower())

    def snapshot(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "entries": dict(sorted((str(k), str(v)) for k, v in self.entries.items())),
        }
        if self.version is not None:
            payload["version"] = str(self.version)
        if self.source is not None:
            payload["source"] = str(self.source)
        return payload


@dataclass(frozen=True)
class AddressRegistry:
    entries: Dict[str, str] = field(default_factory=dict)
    version: Optional[str] = None
    source: Optional[str] = None

    def resolve(self, key: str) -> Optional[str]:
        return self.entries.get(key.strip().lower())

    def snapshot(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "entries": dict(sorted((str(k), str(v)) for k, v in self.entries.items())),
        }
        if self.version is not None:
            payload["version"] = str(self.version)
        if self.source is not None:
            payload["source"] = str(self.source)
        return payload


@dataclass(frozen=True)
class SimulationBackendProfile:
    provider: str = "eth_call"
    mode: str = "deterministic"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "metadata": dict(self.metadata),
        }


class ChainAdapter:
    def __init__(
        self,
        profile: ChainProfile,
        *,
        decoder_registry: Optional[DecoderRegistry] = None,
        strict_mode: bool = True,
    ) -> None:
        self._profile = profile
        self._protocol_registry = ProtocolRegistry(
            entries={k.lower(): str(v) for k, v in profile.protocol_registry.items()},
            version=profile.registry_version,
            source=profile.registry_source,
        )
        self._address_registry = AddressRegistry(
            entries={k.lower(): str(v) for k, v in profile.address_registry.items()},
            version=profile.registry_version,
            source=profile.registry_source,
        )
        backend_cfg = dict(profile.simulation_backend_profile)
        self._simulation_backend = SimulationBackendProfile(
            provider=str(backend_cfg.pop("provider", "eth_call")),
            mode=str(backend_cfg.pop("mode", "deterministic")),
            metadata=backend_cfg,
        )
        self._decoder_registry = decoder_registry or DecoderRegistry()
        self._strict_mode = bool(strict_mode)
        requested = list(profile.decoder_plugins)
        policy = str(profile.decoder_policy or "explicit_only").strip().lower()
        if not requested:
            # `explicit_only` baseline: missing/empty allowlist means "no profile overrides".
            if policy == "explicit_only":
                self._decoder_plugins = []
                return
            raise ConfigurationGuardException(
                human_readable_reason=(
                    "chain_profile.decoder_plugins must be explicitly declared and non-empty."
                ),
                context={
                    "reason": "decoder_plugins_required",
                    "decoder_policy": policy,
                },
            )
        self._decoder_plugins = self._decoder_registry.resolve(
            requested, strict_mode=self._strict_mode
        )

    @property
    def profile(self) -> ChainProfile:
        return self._profile

    def decoder_plugins(self) -> List[DecoderPlugin]:
        return list(self._decoder_plugins)

    def decoder_registry_snapshot(self) -> Dict[str, Any]:
        return self._decoder_registry.snapshot().to_dict()

    def resolve_l3_targets(self) -> Dict[str, Optional[str]]:
        return {
            "multicall3_address": self._profile.multicall3_address,
            "uniswap_v2_router": self._profile.uniswap_v2_router,
        }

    def resolve_protocol_address(self, protocol: str) -> Optional[str]:
        return self._protocol_registry.resolve(protocol)

    def resolve_registered_address(self, key: str) -> Optional[str]:
        return self._address_registry.resolve(key)

    def simulation_backend_profile(self) -> Dict[str, Any]:
        return self._simulation_backend.to_dict()

    def registry_snapshot(self) -> Dict[str, Any]:
        return {
            "protocol_registry": self._protocol_registry.snapshot(),
            "address_registry": self._address_registry.snapshot(),
        }


def build_chain_profile(
    config_chain_id: int, profile_cfg: Optional[Mapping[str, Any]]
) -> ChainProfile:
    profile = dict(profile_cfg or {})
    protocol_registry = dict(profile.get("protocol_registry", {}) or {})
    address_registry = dict(profile.get("address_registry", {}) or {})
    simulation_backend_profile = dict(profile.get("simulation_backend_profile", {}) or {})
    raw_rpc_pol = profile.get("rpc_policy")
    rpc_policy_accepted, rpc_policy_unknown = _partition_rpc_policy(
        raw_rpc_pol if isinstance(raw_rpc_pol, Mapping) else {}
    )
    tail_metadata: Dict[str, Any] = {
        k: v
        for k, v in profile.items()
        if k
        not in {
            "chain_id",
            "registry_version",
            "registry_source",
            "multicall3_address",
            "uniswap_v2_router",
            "profile_name",
            "rpc_policy",
            "protocol_registry",
            "address_registry",
            "decoder_plugins",
            "simulation_backend_profile",
            "chain_constraints",
        }
    }
    if rpc_policy_unknown:
        prior = tail_metadata.get("rpc_policy_extra")
        merged_unknown: Dict[str, Any] = {}
        if isinstance(prior, Mapping):
            merged_unknown.update(dict(prior))
        merged_unknown.update(rpc_policy_unknown)
        tail_metadata = {**tail_metadata, "rpc_policy_extra": merged_unknown}
    raw_decoder_plugins = profile.get("decoder_plugins", [])
    decoder_plugins = [str(x) for x in raw_decoder_plugins if isinstance(x, str)]
    decoder_policy_raw = profile.get("decoder_policy")
    decoder_policy = (
        str(decoder_policy_raw)
        if isinstance(decoder_policy_raw, str) and str(decoder_policy_raw).strip()
        else ("profile_allowlist" if "decoder_plugins" in profile else "explicit_only")
    )
    return ChainProfile(
        chain_id=int(profile.get("chain_id", config_chain_id)),
        profile_name=str(profile.get("profile_name", f"chain_{config_chain_id}_profile")),
        registry_version=(
            str(profile.get("registry_version"))
            if isinstance(profile.get("registry_version"), str)
            and str(profile.get("registry_version")).strip()
            else None
        ),
        registry_source=(
            str(profile.get("registry_source"))
            if isinstance(profile.get("registry_source"), str)
            and str(profile.get("registry_source")).strip()
            else None
        ),
        multicall3_address=profile.get("multicall3_address"),
        uniswap_v2_router=profile.get("uniswap_v2_router"),
        rpc_policy=dict(rpc_policy_accepted),
        protocol_registry={str(k): str(v) for k, v in protocol_registry.items()},
        address_registry={str(k): str(v) for k, v in address_registry.items()},
        decoder_plugins=decoder_plugins,
        simulation_backend_profile=dict(simulation_backend_profile),
        chain_constraints=dict(profile.get("chain_constraints", {}) or {}),
        metadata=dict(tail_metadata),
        decoder_policy=decoder_policy,
    )


def normalize_decoder_plugins(raw_plugins: Iterable[Any]) -> List[DecoderPlugin]:
    return [
        plugin
        for plugin in raw_plugins
        if hasattr(plugin, "can_handle") and hasattr(plugin, "decode_and_collect")
    ]
