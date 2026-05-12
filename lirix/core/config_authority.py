from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from lirix.core.config import LirixConfig
from lirix.core.exceptions import ConfigurationGuardException


def _l3_defaults_for_chain(chain_id: int) -> Dict[str, Any]:
    if int(chain_id) == 1:
        return {
            "multicall3_address": "0xcA11bde05977b3631167028862bE2a173976CA11",
            "uniswap_v2_router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        }
    return {}


def _overlay_non_empty(
    base: Dict[str, Any],
    incoming: Mapping[str, Any],
    source: str,
) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    for key, value in incoming.items():
        if value is None:
            continue
        current = base.get(key)
        if current is not None and current != [] and current != {} and current != "":
            continue
        if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
            continue
        base[key] = value
        tags[key] = source
    return tags


def resolve_config(
    *,
    config: Optional[LirixConfig],
    rpc_urls: Optional[Sequence[str]],
    runtime_patch: Optional[Mapping[str, Any]] = None,
) -> Tuple[LirixConfig, Dict[str, str]]:
    """
    Resolve configuration using strict precedence:
    explicit user input > chain_profile defaults > inferred defaults > runtime_patch.

    This function is the single fallback authority for config resolution and provenance.
    """

    def _apply_runtime_patch(
        *,
        merged: Dict[str, Any],
        patch: Mapping[str, Any],
        allowlist: set[str],
        strict_mode: bool,
        tags: Dict[str, str],
    ) -> None:
        for key, value in patch.items():
            if value is None:
                continue
            current = merged.get(key)
            is_empty = current is None or current == [] or current == {} or current == ""
            if is_empty:
                merged[key] = value
                tags[key] = "runtime"
                continue
            if key in allowlist and current != value:
                merged[key] = value
                tags[key] = "runtime_override"
                continue
            if strict_mode and current != value:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        f"runtime_patch attempted to override `{key}` without allowlist permission."
                    ),
                    context={
                        "reason": "runtime_patch_override_forbidden",
                        "field": key,
                    },
                )

    if config is None:
        cfg = LirixConfig(chain_id=1, rpc_urls=list(rpc_urls or []))
        tags: Dict[str, str] = {
            "chain_id": "inferred",
            "rpc_urls": "explicit" if rpc_urls else "inferred",
        }
        decision_chain: list[str] = ["config:inferred"]
        merged0 = cfg.model_dump(mode="python")
        tags.update(_overlay_non_empty(merged0, _l3_defaults_for_chain(cfg.chain_id), "inferred"))
        decision_chain.append("defaults:l3_inferred")
        if runtime_patch:
            _apply_runtime_patch(
                merged=merged0,
                patch=runtime_patch,
                allowlist=set(),
                strict_mode=bool(cfg.strict_mode),
                tags=tags,
            )
            decision_chain.append("patch:runtime_applied")
            # Special-case: empty chain_profile is still a meaningful governance knob.
            if "chain_profile" in runtime_patch and merged0.get("chain_profile") is None:
                merged0["chain_profile"] = runtime_patch.get("chain_profile")
                tags["chain_profile"] = "runtime"
        decision_chain.append("validate:model")
        tags["__provenance_chain__"] = "inferred>runtime_patch"
        tags["__provenance_decisions__"] = " > ".join(decision_chain)
        base = LirixConfig.model_validate(merged0).with_source_tags(tags)
        return base, tags

    merged = config.model_dump(mode="python")
    source_tags: Dict[str, str] = dict(config.config_source_tags)
    decision_chain = ["config:explicit"]
    profile = dict(config.chain_profile or {})
    profile_defaults: Dict[str, Any] = {
        "multicall3_address": profile.get("multicall3_address"),
        "uniswap_v2_router": profile.get("uniswap_v2_router"),
    }
    source_tags.update(_overlay_non_empty(merged, profile_defaults, "profile"))
    decision_chain.append("defaults:profile_overlay")
    source_tags.update(
        _overlay_non_empty(merged, _l3_defaults_for_chain(config.chain_id), "inferred")
    )
    decision_chain.append("defaults:l3_inferred")
    if rpc_urls is not None:
        merged["rpc_urls"] = list(rpc_urls)
        source_tags["rpc_urls"] = "explicit"
    else:
        source_tags.setdefault("rpc_urls", "explicit")
    if "chain_id" not in source_tags:
        source_tags["chain_id"] = "explicit"
    if runtime_patch:
        _apply_runtime_patch(
            merged=merged,
            patch=runtime_patch,
            allowlist=set(config.runtime_patch_allowlist),
            strict_mode=bool(config.strict_mode),
            tags=source_tags,
        )
        decision_chain.append("patch:runtime_applied")
        if "chain_profile" in runtime_patch and merged.get("chain_profile") is None:
            merged["chain_profile"] = runtime_patch.get("chain_profile")
            source_tags["chain_profile"] = "runtime"
    decision_chain.append("validate:model")
    source_tags["__provenance_chain__"] = "explicit>profile>inferred>runtime_patch"
    source_tags["__provenance_decisions__"] = " > ".join(decision_chain)
    resolved = LirixConfig.model_validate(merged).with_source_tags(source_tags)
    return resolved, source_tags
