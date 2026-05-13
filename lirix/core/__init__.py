# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.core.config import LirixConfig
from lirix.core.config_authority import resolve_config
from lirix.core.constants import (
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
    build_agent_resolution,
    canonicalize_error_code,
    canonicalize_failure_type,
    canonicalize_reason_code,
)
from lirix.core.constants import PREDEFINED_HOOK_POINTS as PREDEFINED_HOOK_POINTS
from lirix.core.evidence import (
    ExecutionEvidence,
    PolicyDecision,
)
from lirix.core.exceptions import (
    HookExecutionException,
    LirixSecurityException,
)
from lirix.core.failure_protocol import (
    build_failure_protocol,
    build_failure_protocol_from_agent_feedback,
    resolve_failure_protocol_to_agent_feedback,
)
from lirix.core.hook_contract import HookAnnotation, HookDecision, HookPatch, ReadonlyHookPayload
from lirix.core.hook_manager import HookManager
from lirix.core.layer_ports import PipelineLayerExecutor, RpcEvidenceSource
from lirix.core.multicall import MulticallEncoder
from lirix.core.session import ExecutionPlan, ValidationSession, verify_replay_bundle

__all__ = [
    # Stable configuration surface
    "LirixConfig",
    "resolve_config",
    "HookManager",
    "HookDecision",
    "HookPatch",
    "HookAnnotation",
    "ReadonlyHookPayload",
    "HOOK_PRE_VALIDATE",
    "HOOK_PRE_SIMULATION",
    "HOOK_POST_VALIDATE",
    "HOOK_POST_SIMULATION",
    # Canonical semantics and remediation protocol
    "canonicalize_error_code",
    "canonicalize_reason_code",
    "canonicalize_failure_type",
    "build_agent_resolution",
    "build_failure_protocol",
    "build_failure_protocol_from_agent_feedback",
    "resolve_failure_protocol_to_agent_feedback",
    # Evidence and replay
    "ExecutionEvidence",
    "PolicyDecision",
    "ExecutionPlan",
    "ValidationSession",
    "verify_replay_bundle",
    # Stable exception types
    "LirixSecurityException",
    "HookExecutionException",
    # Dependency inversion protocols (L4/L5 wiring contracts for facades and typing)
    "PipelineLayerExecutor",
    "RpcEvidenceSource",
    # Explicitly supported multicall encoder
    "MulticallEncoder",
]
