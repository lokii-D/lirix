# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Module-level client facades (replay, chain profile, hooks)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Sequence

from lirix.core import session as _session_module
from lirix.core.config import LirixConfig
from lirix.core.hook_manager import HookCallback, HookManager

if TYPE_CHECKING:
    from lirix._facade import Lirix


def register_hook(manager: HookManager, hook_point: str, callback: HookCallback) -> None:
    """注册插件钩子（与 HookManager.register_hook 等价，便于顶层 API 暴露）。"""
    manager.register_hook(hook_point, callback)


def build_for_chain_profile(
    profile: Mapping[str, Any],
    *,
    base_config: Optional[LirixConfig] = None,
    rpc_urls: Optional[Sequence[str]] = None,
    runtime_patch: Optional[Mapping[str, Any]] = None,
) -> Lirix:
    """
    Build a Lirix instance using an explicit chain_profile mapping.

    This is a guided, low-misuse entrypoint: profile drives chain surface defaults,
    while explicit config fields and runtime_patch preserve their precedence rules.
    """
    from lirix._facade import Lirix

    profile_dict = dict(profile)
    if base_config is None:
        chain_id = int(profile_dict.get("chain_id", 1))
        cfg = LirixConfig(
            chain_id=chain_id,
            rpc_urls=list(rpc_urls or []),
            chain_profile=profile_dict,
        )
    else:
        cfg = base_config.model_copy(update={"chain_profile": profile_dict})
    return Lirix(config=cfg, rpc_urls=list(rpc_urls or []), runtime_patch=runtime_patch)


def replay_session(
    bundle: Mapping[str, Any],
    *,
    enforce_agent_timeline_order: bool = False,
    enforce_replay_proof_strict: bool = False,
) -> Mapping[str, Any]:
    """
    Verify a replay bundle and return the embedded session payload snapshot.

    No chain-side re-execution is performed (zero-telemetry, local-only).
    """
    # Resolve via `lirix.core.session` so tests can patch `lirix.core.session.verify_replay_bundle`.
    if not enforce_agent_timeline_order and not enforce_replay_proof_strict:
        _session_module.verify_replay_bundle(bundle)
    else:
        _session_module.verify_replay_bundle(
            bundle,
            enforce_agent_timeline_order=enforce_agent_timeline_order,
            enforce_replay_proof_strict=enforce_replay_proof_strict,
        )
    payload = bundle.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def resolve_failure_protocol(exc_or_bundle_context: Mapping[str, Any]) -> Dict[str, Any]:
    """Backward-compatible module-level facade for failure_protocol resolution."""
    from lirix._facade import Lirix

    return Lirix.resolve_failure_protocol(exc_or_bundle_context)
