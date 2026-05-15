# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

import sys

from lirix._client_facade import (
    build_for_chain_profile,
    register_hook,
    replay_session,
    resolve_failure_protocol,
)
from lirix._facade import Lirix
from lirix._multicall_facade import atomic_multicall
from lirix.core import LirixConfig, LirixSecurityException, PipelineLayerExecutor, RpcEvidenceSource
from lirix.core.hook_manager import HookManager
from lirix.core.session import verify_replay_bundle
from lirix.core.signatures import SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR
from lirix.layers import ProxyPiercer, RPCManager, SandboxSimulator

__version__ = "2.0.4"

if sys.version_info < (3, 9) or sys.version_info >= (3, 15):
    raise ImportError("Lirix requires Python 3.9 through 3.14.")

__all__ = [
    "Lirix",
    "LirixConfig",
    "LirixSecurityException",
    "HookManager",
    "PipelineLayerExecutor",
    "RpcEvidenceSource",
    "SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR",
    "ProxyPiercer",
    "RPCManager",
    "SandboxSimulator",
    "atomic_multicall",
    "build_for_chain_profile",
    "register_hook",
    "replay_session",
    "resolve_failure_protocol",
    "verify_replay_bundle",
]
