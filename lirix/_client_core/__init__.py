# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii
# ruff: noqa: I001

"""Lirix client (:class:`Lirix`) and pipeline-facing module helpers.

Direct imports of :mod:`lirix._client_core` are **internal compatibility only** (patch points,
migration tools). Public callers should use ``from lirix import Lirix`` and the supported root
helpers instead.
"""

from __future__ import annotations

from lirix._client_facade import (  # noqa: E402
    build_for_chain_profile,
    register_hook,
    replay_session,
    resolve_failure_protocol,
)
from lirix._facade import Lirix  # noqa: E402

# Internal pipeline components (compat patch points only; NOT part of __all__).
from lirix.core.evidence import rejected_step_to_agent_feedback  # noqa: E402,F401
from lirix.core.hook_manager import HookManager  # noqa: E402,F401
from lirix.core.session import verify_replay_bundle  # noqa: E402
from lirix.layers.l1_intent_validator import IntentValidator as IntentValidator  # noqa: E402,F401
from lirix.layers.l2_schema_validator import SchemaValidator as SchemaValidator  # noqa: E402,F401
from lirix.layers.l3_defi_parser import DeFiPayloadParser as DeFiPayloadParser  # noqa: E402,F401
from lirix.layers.l4_rpc_manager import RPCManager as RPCManager  # noqa: E402,F401
from lirix.layers.l5_sandbox_simulator import (
    SandboxSimulator as SandboxSimulator,
)  # noqa: E402,F401

__all__ = [
    "Lirix",
    "build_for_chain_profile",
    "register_hook",
    "replay_session",
    "resolve_failure_protocol",
    "verify_replay_bundle",
]
