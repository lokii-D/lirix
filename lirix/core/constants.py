from __future__ import annotations

from typing import Any, Dict, Final, FrozenSet, Optional

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
