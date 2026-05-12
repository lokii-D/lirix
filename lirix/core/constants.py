# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Dict, Final, FrozenSet, Literal, Optional

PYTHON_SUPPORT_MIN: Final[tuple[int, int]] = (3, 9)
PYTHON_SUPPORT_MAX_EXCLUSIVE: Final[tuple[int, int]] = (3, 15)
SECURITY_TRACE_SCHEMA_VERSION: Final[str] = "1.0"
HOOK_CONTRACT_SCHEMA_VERSION: Final[str] = "1.0"
RPC_EVIDENCE_SCHEMA_VERSION: Final[str] = "2.0"
POLICY_LIFECYCLE_SCHEMA_VERSION: Final[str] = "1.0"
AGENT_FEEDBACK_SCHEMA_VERSION: Final[str] = "1.0"

HookContractMode = Literal["legacy", "warn", "shadow", "enforce"]
PolicyLifecycleMode = Literal["digest_verified"]
RPCEvidenceMode = Literal["v2_only"]


def normalize_policy_lifecycle_mode(mode: str) -> str:
    """Map deprecated config labels to effective runtime mode."""
    if mode == "signed_only":
        return "digest_verified"
    return mode


def policy_lifecycle_integrity_enforced(mode: str) -> bool:
    """True when policy rows must match a SHA256 integrity digest (not asymmetric sig)."""
    return normalize_policy_lifecycle_mode(mode) == "digest_verified"


HookFailureLevel = Literal["fatal", "soft", "observe_only"]

# Hook 点位（仅注册与调度，不含业务逻辑）
HOOK_PRE_VALIDATE: Final[str] = "pre_validate"
HOOK_POST_VALIDATE: Final[str] = "post_validate"
HOOK_PRE_SIMULATION: Final[str] = "pre_simulation"
HOOK_POST_SIMULATION: Final[str] = "post_simulation"
HOOK_ON_AUDIT_LOG: Final[str] = "on_audit_log"
HOOK_RPC_FALLBACK: Final[str] = "rpc_fallback"
# L1–L5 与 Multicall 打包节点（扩展隔离执行，不承载业务逻辑）
HOOK_LAYER_L1: Final[str] = "layer_l1_validate"
HOOK_LAYER_L2: Final[str] = "layer_l2_validate"
HOOK_LAYER_L3: Final[str] = "layer_l3_validate"
HOOK_LAYER_L4: Final[str] = "layer_l4_rpc"
HOOK_LAYER_L5: Final[str] = "layer_l5_simulation"
HOOK_MULTICALL_PACK: Final[str] = "multicall_pack"
# 隔离钩子默认墙钟超时（秒）；防 Agent 被慢插件拖死，可用 None 关闭（仅 invoke_hooks_isolated）
HOOK_ISOLATED_TIMEOUT_SEC: Final[float] = 0.5

PREDEFINED_HOOK_POINTS: Final[FrozenSet[str]] = frozenset(
    {
        HOOK_PRE_VALIDATE,
        HOOK_POST_VALIDATE,
        HOOK_PRE_SIMULATION,
        HOOK_POST_SIMULATION,
        HOOK_ON_AUDIT_LOG,
        HOOK_RPC_FALLBACK,
        HOOK_LAYER_L1,
        HOOK_LAYER_L2,
        HOOK_LAYER_L3,
        HOOK_LAYER_L4,
        HOOK_LAYER_L5,
        HOOK_MULTICALL_PACK,
    }
)

HOOK_PAYLOAD_REQUIRED_FIELDS: Final[Dict[str, FrozenSet[str]]] = {
    HOOK_PRE_VALIDATE: frozenset({"intent", "payload"}),
    HOOK_POST_VALIDATE: frozenset({"intent", "payload"}),
    HOOK_PRE_SIMULATION: frozenset({"intent", "payload"}),
    HOOK_POST_SIMULATION: frozenset({"intent", "payload", "simulation"}),
    HOOK_LAYER_L4: frozenset({"layer", "block_number", "mode"}),
    HOOK_LAYER_L5: frozenset({"layer", "block_number", "simulation"}),
    HOOK_MULTICALL_PACK: frozenset({"encoded", "subcall_count"}),
}

HOOK_FAILURE_LEVELS: Final[FrozenSet[str]] = frozenset({"fatal", "soft", "observe_only"})
DEFAULT_HOOK_FAILURE_LEVEL: Final[HookFailureLevel] = "soft"
HOOK_PATCH_ALLOWED_POINTS: Final[FrozenSet[str]] = frozenset(
    {HOOK_PRE_VALIDATE, HOOK_PRE_SIMULATION}
)
HOOK_ERR_PATCH_TARGET_FORBIDDEN: Final[str] = "LIRIX_HOOK_PATCH_TARGET_FORBIDDEN"
HOOK_WARN_PATCH_TARGET_SHADOW: Final[str] = "LIRIX_HOOK_PATCH_TARGET_SHADOW_WARNING"
HOOK_WARN_PATCH_TARGET: Final[str] = "LIRIX_HOOK_PATCH_TARGET_WARNING"
HOOK_ERR_PATCH_FORBIDDEN: Final[str] = "LIRIX_HOOK_PATCH_FORBIDDEN"
HOOK_WARN_PATCH_FORBIDDEN_SHADOW: Final[str] = "LIRIX_HOOK_PATCH_FORBIDDEN_SHADOW_WARNING"
HOOK_WARN_PATCH_FORBIDDEN: Final[str] = "LIRIX_HOOK_PATCH_FORBIDDEN_WARNING"
HOOK_ERR_DECISION_REJECTED: Final[str] = "LIRIX_HOOK_DECISION_REJECTED"
HOOK_ERR_CONTRACT_VIOLATION: Final[str] = "LIRIX_HOOK_CONTRACT_VIOLATION"
HOOK_WARN_CONTRACT_SHADOW: Final[str] = "LIRIX_HOOK_CONTRACT_SHADOW_WARNING"
HOOK_WARN_CONTRACT: Final[str] = "LIRIX_HOOK_CONTRACT_WARNING"
HOOK_ERR_TIMEOUT: Final[str] = "LIRIX_HOOK_TIMEOUT"
HOOK_ERR_RUNTIME: Final[str] = "LIRIX_HOOK_RUNTIME_ERROR"
HOOK_ERR_ASYNC_REQUIRED: Final[str] = "LIRIX_HOOK_ASYNC_REQUIRED"


def _hook_point_capabilities() -> Dict[str, Dict[str, Any]]:
    trace_hooks = frozenset(
        {
            HOOK_PRE_VALIDATE,
            HOOK_PRE_SIMULATION,
            HOOK_POST_SIMULATION,
            HOOK_POST_VALIDATE,
            HOOK_LAYER_L1,
            HOOK_LAYER_L2,
            HOOK_LAYER_L3,
            HOOK_LAYER_L4,
            HOOK_LAYER_L5,
        }
    )
    return {
        p: {
            "allows_patch": p in HOOK_PATCH_ALLOWED_POINTS,
            "requires_trace": p in trace_hooks,
        }
        for p in PREDEFINED_HOOK_POINTS
    }


HOOK_POINT_CAPABILITIES: Final[Dict[str, Dict[str, Any]]] = _hook_point_capabilities()

RPC_REASON_TRANSPORT_ERROR: Final[str] = "transport_error"
RPC_REASON_TIMEOUT: Final[str] = "timeout"
RPC_REASON_MALFORMED_RESPONSE: Final[str] = "malformed_response"
RPC_REASON_STALE_NODE: Final[str] = "stale_node"
RPC_REASON_INCONSISTENT_RESULT: Final[str] = "inconsistent_result"
RPC_REASON_SUSPICIOUS_CONSISTENCY: Final[str] = "suspicious_consistency"
RPC_REASON_CONSENSUS_FAILURE: Final[str] = "consensus_failure"
RPC_REASON_NONE: Final[str] = "none"

# 机器可读自愈指令（供 Agent / LLM 直接消费），JSON Schema 草案描述
RESOLUTION_FOR_AGENT_JSON_SCHEMA: Final[Dict[str, Any]] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "LirixAgentResolution",
    "type": "object",
    "required": ["action", "schema_version"],
    "properties": {
        "action": {"type": "string", "description": "建议执行的修复动作标识"},
        "schema_version": {"type": "integer", "const": 1},
        "target_field": {"type": "string"},
        "retry": {"type": "boolean"},
        "hook_point": {"type": "string"},
        "notes": {"type": "string"},
    },
    "additionalProperties": True,
}


def build_agent_resolution(
    *,
    action: str,
    target_field: Optional[str] = None,
    retry: bool = False,
    hook_point: Optional[str] = None,
    notes: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构造符合 RESOLUTION_FOR_AGENT_JSON_SCHEMA 的最小合规 dict。"""
    payload: Dict[str, Any] = {
        "action": action,
        "schema_version": 1,
        "retry": retry,
    }
    if target_field is not None:
        payload["target_field"] = target_field
    if hook_point is not None:
        payload["hook_point"] = hook_point
    if notes is not None:
        payload["notes"] = notes
    payload.update(extra)
    return payload


# 错误码（全局必须以 LIRIX_ERR_ 前缀命名）
LIRIX_ERR_CIRCUIT_BREAKER_OPEN: Final[str] = "LIRIX_ERR_CIRCUIT_BREAKER_OPEN"
LIRIX_ERR_INVALID_INTENT: Final[str] = "LIRIX_ERR_INVALID_INTENT"
LIRIX_ERR_CONFIGURATION_GUARD: Final[str] = "LIRIX_ERR_CONFIGURATION_GUARD"
LIRIX_ERR_HOOK_EXECUTION: Final[str] = "LIRIX_ERR_HOOK_EXECUTION"
LIRIX_ERR_RPC_UNAVAILABLE: Final[str] = "LIRIX_ERR_RPC_UNAVAILABLE"
LIRIX_ERR_VALIDATION_FAILED: Final[str] = "LIRIX_ERR_VALIDATION_FAILED"
LIRIX_ERR_HOOK_UNKNOWN_POINT: Final[str] = "LIRIX_ERR_HOOK_UNKNOWN_POINT"
LIRIX_ERR_HOOK_ASYNC_REQUIRED: Final[str] = "LIRIX_ERR_HOOK_ASYNC_REQUIRED"
LIRIX_ERR_ADDRESS_CHECKSUM: Final[str] = "LIRIX_ERR_ADDRESS_CHECKSUM"
LIRIX_ERR_SCHEMA_VALIDATION: Final[str] = "LIRIX_ERR_SCHEMA_VALIDATION"
LIRIX_ERR_MALICIOUS_PAYLOAD: Final[str] = "LIRIX_ERR_MALICIOUS_PAYLOAD"
LIRIX_ERR_SIMULATION_FAILED: Final[str] = "LIRIX_ERR_SIMULATION_FAILED"
LIRIX_ERR_MULTICALL_ENCODING: Final[str] = "LIRIX_ERR_MULTICALL_ENCODING"
LIRIX_ERR_DEFI_SLIPPAGE_MISSING: Final[str] = "LIRIX_ERR_DEFI_SLIPPAGE_MISSING"
LIRIX_ERR_RPC_QUOTA_EXHAUSTED: Final[str] = "LIRIX_ERR_RPC_QUOTA_EXHAUSTED"
LIRIX_ERR_INSUFFICIENT_FEE: Final[str] = "LIRIX_ERR_INSUFFICIENT_FEE"
LIRIX_ERR_NONCE_DESYNC: Final[str] = "LIRIX_ERR_NONCE_DESYNC"
LIRIX_ERR_CONTRACT_PAUSED: Final[str] = "LIRIX_ERR_CONTRACT_PAUSED"
LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT: Final[str] = "LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT"

# Canonical error codes for legacy LRX_* surfaces.
# These do NOT change existing LRX_* exceptions; they are used for governance/replay closure.
LIRIX_ERR_RPC_CONSENSUS_FAILED: Final[str] = "LIRIX_ERR_RPC_CONSENSUS_FAILED"
LIRIX_ERR_RPC_QUORUM_FAILED: Final[str] = "LIRIX_ERR_RPC_QUORUM_FAILED"
LIRIX_ERR_POLICY_BLOCKED: Final[str] = "LIRIX_ERR_POLICY_BLOCKED"
LIRIX_ERR_LEGACY_ERROR: Final[str] = "LIRIX_ERR_LEGACY_ERROR"

LEGACY_TO_CANONICAL_ERROR_CODE: Final[Dict[str, str]] = {
    # RPC (L4)
    "LRX_L4_CONSENSUS_FAILED": LIRIX_ERR_RPC_CONSENSUS_FAILED,
    "LRX_RPC_QUORUM_FAILED": LIRIX_ERR_RPC_QUORUM_FAILED,
    # Policy (shadow auditor)
    "LRX_SHADOW_POLICY_BLOCKED": LIRIX_ERR_POLICY_BLOCKED,
    # Exception adapter default
    "LRX_LEGACY_ERROR": LIRIX_ERR_LEGACY_ERROR,
    # Core guard/builder/translator
    "LRX_SIM_ASYNC_PAYLOAD": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_TIMEOUT_BLOCK": LIRIX_ERR_RPC_UNAVAILABLE,
    "LRX_SIM_TARGET_REQUIRED": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_SIM_ARGS_TYPE": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_SIM_SIGNATURE_REQUIRED": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_VALIDATION_ARG_COUNT": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_VALIDATION_ABI_ENCODE": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_VALIDATION_NUMERIC_TYPE": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_VALIDATION_SIGNATURE_EMPTY": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_VALIDATION_SIGNATURE_FORMAT": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_INTENT_TYPE_UNSUPPORTED": LIRIX_ERR_INVALID_INTENT,
    "LRX_INTENT_MISSING_FIELDS": LIRIX_ERR_INVALID_INTENT,
    "LRX_BRIDGE_SIGNATURE_UNSUPPORTED": LIRIX_ERR_INVALID_INTENT,
    "LRX_BRIDGE_PROTOCOL_UNSUPPORTED": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_BRIDGE_ROUTE_UNSUPPORTED": LIRIX_ERR_VALIDATION_FAILED,
    "LRX_HALLUCINATION_ADDRESS": LIRIX_ERR_MALICIOUS_PAYLOAD,
    # Shield/simulation path
    "LRX_ASSERTION_CONFIG_INVALID": LIRIX_ERR_CONFIGURATION_GUARD,
    "LRX_HONEYPOT_DETECTED": LIRIX_ERR_MALICIOUS_PAYLOAD,
    "LRX_STATE_MISMATCH": LIRIX_ERR_SIMULATION_FAILED,
    "LRX_DEP_SIMULATION_MISSING": LIRIX_ERR_SIMULATION_FAILED,
    "LRX_SIM_CONTRACT_LOGIC": LIRIX_ERR_SIMULATION_FAILED,
    "LRX_SIM_WEB3_ERROR": LIRIX_ERR_RPC_UNAVAILABLE,
    "LRX_SIM_VALUE_ERROR": LIRIX_ERR_SIMULATION_FAILED,
}
CANONICAL_ERROR_CODE_KNOWN: Final[FrozenSet[str]] = frozenset(
    {
        LIRIX_ERR_CIRCUIT_BREAKER_OPEN,
        LIRIX_ERR_INVALID_INTENT,
        LIRIX_ERR_CONFIGURATION_GUARD,
        LIRIX_ERR_HOOK_EXECUTION,
        LIRIX_ERR_RPC_UNAVAILABLE,
        LIRIX_ERR_VALIDATION_FAILED,
        LIRIX_ERR_HOOK_UNKNOWN_POINT,
        LIRIX_ERR_HOOK_ASYNC_REQUIRED,
        LIRIX_ERR_ADDRESS_CHECKSUM,
        LIRIX_ERR_SCHEMA_VALIDATION,
        LIRIX_ERR_MALICIOUS_PAYLOAD,
        LIRIX_ERR_SIMULATION_FAILED,
        LIRIX_ERR_MULTICALL_ENCODING,
        LIRIX_ERR_DEFI_SLIPPAGE_MISSING,
        LIRIX_ERR_RPC_QUOTA_EXHAUSTED,
        LIRIX_ERR_INSUFFICIENT_FEE,
        LIRIX_ERR_NONCE_DESYNC,
        LIRIX_ERR_CONTRACT_PAUSED,
        LIRIX_ERR_RPC_CONSENSUS_FAILED,
        LIRIX_ERR_RPC_QUORUM_FAILED,
        LIRIX_ERR_POLICY_BLOCKED,
        LIRIX_ERR_LEGACY_ERROR,
        LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT,
    }
)


def canonicalize_error_code(raw: Any, *, strict: bool = False) -> str:
    """
    Best-effort canonicalization of legacy error codes into LIRIX_ERR_* taxonomy.

    Compatibility: does not reject unknown codes; returns normalized string.
    """
    token = str(raw or "").strip()
    if not token:
        return LIRIX_ERR_LEGACY_ERROR
    canonical = LEGACY_TO_CANONICAL_ERROR_CODE.get(token, token)
    if strict and canonical not in CANONICAL_ERROR_CODE_KNOWN:
        return LIRIX_ERR_LEGACY_ERROR
    return canonical


# Agent feedback reason codes: fixed taxonomy for stable downstream automation.
AGENT_FEEDBACK_REASON_OK: Final[str] = "LIRIX_REASON_OK"
AGENT_FEEDBACK_REASON_UNKNOWN: Final[str] = "LIRIX_REASON_UNKNOWN"
AGENT_FEEDBACK_REASON_TIMEOUT: Final[str] = "LIRIX_REASON_TIMEOUT"
AGENT_FEEDBACK_REASON_TRANSPORT_ERROR: Final[str] = "LIRIX_REASON_TRANSPORT_ERROR"
AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE: Final[str] = "LIRIX_REASON_CONSENSUS_FAILURE"
AGENT_FEEDBACK_REASON_SCHEMA_INVALID: Final[str] = "LIRIX_REASON_SCHEMA_INVALID"
AGENT_FEEDBACK_REASON_INTENT_INVALID: Final[str] = "LIRIX_REASON_INTENT_INVALID"
AGENT_FEEDBACK_REASON_POLICY_VIOLATION: Final[str] = "LIRIX_REASON_POLICY_VIOLATION"
AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE: Final[str] = (
    "LIRIX_REASON_RECONCILE_PARTIAL_FAILURE"
)

AGENT_FEEDBACK_REASON_CODE_MAP: Final[Dict[str, str]] = {
    "ok": AGENT_FEEDBACK_REASON_OK,
    "timeout": AGENT_FEEDBACK_REASON_TIMEOUT,
    "transport_error": AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
    "consensus_failure": AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    "schema_validation_failed": AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
    "invalid_intent": AGENT_FEEDBACK_REASON_INTENT_INVALID,
    "policy_violation": AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
    "reconcile_partial_failure": AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE,
    "reconcile_failed": AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE,
    "height_spread_exceeded": AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    "hook_blocked": AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
    "schema_invalid": AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
    "rpc_error": AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
}
AGENT_FEEDBACK_REASON_KNOWN: Final[FrozenSet[str]] = frozenset(
    {
        AGENT_FEEDBACK_REASON_OK,
        AGENT_FEEDBACK_REASON_UNKNOWN,
        AGENT_FEEDBACK_REASON_TIMEOUT,
        AGENT_FEEDBACK_REASON_TRANSPORT_ERROR,
        AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
        AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
        AGENT_FEEDBACK_REASON_INTENT_INVALID,
        AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
        AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE,
    }
)

# Canonical failure type taxonomy used by failure_protocol/session/replay consumers.
FAILURE_TYPE_NONE: Final[str] = "none"
FAILURE_TYPE_TIMEOUT: Final[str] = "timeout"
FAILURE_TYPE_TRANSPORT_ERROR: Final[str] = "transport_error"
FAILURE_TYPE_CONSENSUS_FAILURE: Final[str] = "consensus_failure"
FAILURE_TYPE_SCHEMA_VALIDATION_FAILED: Final[str] = "schema_validation_failed"
FAILURE_TYPE_INVALID_INTENT: Final[str] = "invalid_intent"
FAILURE_TYPE_POLICY_VIOLATION: Final[str] = "policy_violation"
FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE: Final[str] = "reconcile_partial_failure"
FAILURE_TYPE_SECURITY_REJECTION: Final[str] = "security_rejection"
FAILURE_TYPE_UNKNOWN: Final[str] = "unknown"

CANONICAL_FAILURE_TYPE_MAP: Final[Dict[str, str]] = {
    "ok": FAILURE_TYPE_NONE,
    "none": FAILURE_TYPE_NONE,
    "timeout": FAILURE_TYPE_TIMEOUT,
    "transport_error": FAILURE_TYPE_TRANSPORT_ERROR,
    "consensus_failure": FAILURE_TYPE_CONSENSUS_FAILURE,
    "schema_validation_failed": FAILURE_TYPE_SCHEMA_VALIDATION_FAILED,
    "invalid_intent": FAILURE_TYPE_INVALID_INTENT,
    "policy_violation": FAILURE_TYPE_POLICY_VIOLATION,
    "reconcile_partial_failure": FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
    "reconcile_failed": FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
    "height_spread_exceeded": FAILURE_TYPE_CONSENSUS_FAILURE,
    "hook_blocked": FAILURE_TYPE_POLICY_VIOLATION,
    "schema_invalid": FAILURE_TYPE_SCHEMA_VALIDATION_FAILED,
    "rpc_error": FAILURE_TYPE_TRANSPORT_ERROR,
    "security_rejection": FAILURE_TYPE_SECURITY_REJECTION,
}

_REASON_CODE_FALLBACK_FROM_ERROR: Final[Dict[str, str]] = {
    LIRIX_ERR_RPC_CONSENSUS_FAILED: AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    LIRIX_ERR_RPC_QUORUM_FAILED: AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE,
    LIRIX_ERR_POLICY_BLOCKED: AGENT_FEEDBACK_REASON_POLICY_VIOLATION,
    LIRIX_ERR_SCHEMA_VALIDATION: AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
    LIRIX_ERR_INVALID_INTENT: AGENT_FEEDBACK_REASON_INTENT_INVALID,
    LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT: AGENT_FEEDBACK_REASON_SCHEMA_INVALID,
}

_REASON_TO_FAILURE_TYPE: Final[Dict[str, str]] = {
    AGENT_FEEDBACK_REASON_OK: FAILURE_TYPE_NONE,
    AGENT_FEEDBACK_REASON_TIMEOUT: FAILURE_TYPE_TIMEOUT,
    AGENT_FEEDBACK_REASON_TRANSPORT_ERROR: FAILURE_TYPE_TRANSPORT_ERROR,
    AGENT_FEEDBACK_REASON_CONSENSUS_FAILURE: FAILURE_TYPE_CONSENSUS_FAILURE,
    AGENT_FEEDBACK_REASON_SCHEMA_INVALID: FAILURE_TYPE_SCHEMA_VALIDATION_FAILED,
    AGENT_FEEDBACK_REASON_INTENT_INVALID: FAILURE_TYPE_INVALID_INTENT,
    AGENT_FEEDBACK_REASON_POLICY_VIOLATION: FAILURE_TYPE_POLICY_VIOLATION,
    AGENT_FEEDBACK_REASON_RECONCILE_PARTIAL_FAILURE: FAILURE_TYPE_RECONCILE_PARTIAL_FAILURE,
}


def is_known_reason_code(raw: Any) -> bool:
    token = str(raw or "").strip()
    return token in AGENT_FEEDBACK_REASON_KNOWN


def canonicalize_reason_code(
    raw: Any, *, fallback_error_code: Any = None, strict: bool = False
) -> str:
    """Normalize any reason token into the fixed AGENT_FEEDBACK reason taxonomy."""
    token = str(raw or "").strip()
    if token.startswith("LIRIX_REASON_"):
        if strict and token not in AGENT_FEEDBACK_REASON_KNOWN:
            return AGENT_FEEDBACK_REASON_UNKNOWN
        return token
    lowered = token.lower()
    if lowered in AGENT_FEEDBACK_REASON_CODE_MAP:
        return AGENT_FEEDBACK_REASON_CODE_MAP[lowered]
    if fallback_error_code is not None:
        canonical_error = canonicalize_error_code(fallback_error_code)
        mapped = _REASON_CODE_FALLBACK_FROM_ERROR.get(canonical_error)
        if mapped is not None:
            return mapped
    return AGENT_FEEDBACK_REASON_UNKNOWN


def canonicalize_failure_type(raw: Any, *, fallback_reason_code: Any = None) -> str:
    """Normalize failure type tokens into the canonical failure_type taxonomy."""
    token = str(raw or "").strip().lower()
    if token in CANONICAL_FAILURE_TYPE_MAP:
        return CANONICAL_FAILURE_TYPE_MAP[token]
    if fallback_reason_code is not None:
        reason = canonicalize_reason_code(fallback_reason_code)
        mapped = _REASON_TO_FAILURE_TYPE.get(reason)
        if mapped is not None:
            return mapped
    return FAILURE_TYPE_UNKNOWN
