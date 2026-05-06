# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

__version__ = "1.6.0"

import sys

if sys.version_info < (3, 8) or sys.version_info >= (3, 15):
    raise ImportError("Lirix requires Python 3.8 through 3.14.")

from typing import Any, Dict, Mapping, Optional, Sequence, cast

from web3 import Web3
from web3.types import StateOverride

from lirix.audit.logger import AuditLogger
from lirix.core import (
    AddressChecksumException,
    CircuitBreakerOpenException,
    ConfigurationGuardException,
    HookAsyncContextException,
    HookExecutionException,
    HookManager,
    HookUnknownPointException,
    InvalidIntentException,
    LirixConfig,
    LirixSecurityException,
    MaliciousPayloadException,
    MulticallEncodingException,
    RPCUnavailableException,
    SchemaValidationException,
    SimulationFailedException,
    ValidationFailedException,
)
from lirix.core.constants import (
    HOOK_ISOLATED_TIMEOUT_SEC,
    HOOK_MULTICALL_PACK,
    HOOK_POST_SIMULATION,
    HOOK_POST_VALIDATE,
    HOOK_PRE_SIMULATION,
    HOOK_PRE_VALIDATE,
)
from lirix.core.hook_manager import HookCallback
from lirix.core.multicall import MulticallEncoder
from lirix.core.signatures import AGGREGATE3_SELECTOR, AGGREGATE3_VALUE_SELECTOR
from lirix.layers import (
    AbiLRUCache,
    DeFiPayloadParser,
    IntentValidator,
    ProxyPiercer,
    RPCManager,
    SandboxSimulator,
    SchemaValidator,
    ShadowAuditor,
    ShadowPolicySchema,
)

__all__ = [
    "Guardian",
    "AddressChecksumException",
    "AuditLogger",
    "CircuitBreakerOpenException",
    "ConfigurationGuardException",
    "HookAsyncContextException",
    "HookExecutionException",
    "HookManager",
    "HookUnknownPointException",
    "InvalidIntentException",
    "Lirix",
    "LirixConfig",
    "LirixSecurityException",
    "MaliciousPayloadException",
    "MulticallEncoder",
    "MulticallEncodingException",
    "RPCUnavailableException",
    "SchemaValidationException",
    "SimulationFailedException",
    "ValidationFailedException",
    "RPCManager",
    "SandboxSimulator",
    "ProxyPiercer",
    "AbiLRUCache",
    "ShadowAuditor",
    "ShadowPolicySchema",
    "atomic_multicall",
    "register_hook",
]


def register_hook(manager: HookManager, hook_point: str, callback: HookCallback) -> None:
    """注册插件钩子（与 HookManager.register_hook 等价，便于顶层 API 暴露）。"""
    manager.register_hook(hook_point, callback)


def _resolve_multicall3_address(config: LirixConfig) -> str:
    if config.multicall3_address:
        return str(config.multicall3_address)
    if config.chain_id == 1:
        return Web3.to_checksum_address("0xcA11bde05977b3631167028862bE2a173976CA11")
    raise ConfigurationGuardException(
        human_readable_reason=(
            "atomic_multicall requires multicall3_address for non-mainnet chain_id."
        ),
        context={"chain_id": config.chain_id},
    )


def atomic_multicall(
    client: Lirix,
    intent: str,
    transactions: Sequence[Mapping[str, Any]],
    *,
    outer_value_wei: Optional[int] = None,
) -> Dict[str, Any]:
    """将多笔子交易原子编码为 Multicall3 单笔 calldata，并走 L1→L3 校验；不签名、不广播。"""
    mc = _resolve_multicall3_address(client.config)
    encoder = MulticallEncoder(mc)
    encoded = encoder.encode_transactions(
        [dict(x) for x in transactions],
        outer_value_wei=outer_value_wei,
    )
    client.hooks.invoke_hooks_isolated(
        HOOK_MULTICALL_PACK,
        encoded=encoded,
        subcall_count=len(transactions),
        timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
    )
    data = encoded["data"]
    sel = bytes.fromhex(data[2:10])
    if sel == AGGREGATE3_VALUE_SELECTOR:
        fn = "aggregate3Value"
    elif sel == AGGREGATE3_SELECTOR:
        fn = "aggregate3"
    else:
        raise MulticallEncodingException(
            human_readable_reason="Encoded calldata selector is not Multicall3 aggregate3 family.",
            context={"selector": data[2:10]},
        )
    payload = {
        "to": encoded["to"],
        "data": encoded["data"],
        "value": encoded["value"],
        "function_name": fn,
    }
    client.chain_validate(intent, payload)
    return {"encoded": encoded, "payload": payload}


class Lirix:
    """三行接入示例：配置 / 调度 / 审计。"""

    def __init__(
        self,
        config: Optional[LirixConfig] = None,
        *,
        rpc_urls: Optional[Sequence[str]] = None,
    ) -> None:
        if config is None:
            self.config = LirixConfig(chain_id=1, rpc_urls=list(rpc_urls or []))
        elif rpc_urls is not None:
            self.config = config.model_copy(update={"rpc_urls": list(rpc_urls)})
        else:
            self.config = config
        self.hooks = HookManager()
        self.audit = AuditLogger(hook_manager=self.hooks)
        self.hooks.bind_audit_logger(self.audit)

    def chain_validate(self, intent: str, payload: Mapping[str, Any]) -> bool:
        """L1→L2→L3 串联校验；任一层失败抛出 LirixSecurityException 子类并终止。"""
        draft = dict(payload)
        self.hooks.invoke_hooks_isolated(
            HOOK_PRE_VALIDATE,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        IntentValidator(self.config, hooks=self.hooks).validate(intent, draft)
        SchemaValidator(hooks=self.hooks).validate(draft)
        DeFiPayloadParser(self.config, hooks=self.hooks).validate(draft)
        self.hooks.invoke_hooks_isolated(
            HOOK_POST_VALIDATE,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        return True

    def validate_and_simulate(
        self,
        intent: str,
        payload: Mapping[str, Any],
        *,
        state_overrides: Optional[Dict[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """L1→L2→L3→L4→L5：校验后做零 Gas eth_call 沙盒模拟（同步）。

        state_overrides: EIP-3155 状态覆盖，经 L5 透传为 eth_call 的 state_override。
        """
        draft = dict(payload)
        self.hooks.invoke_hooks_isolated(
            HOOK_PRE_VALIDATE,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        IntentValidator(self.config, hooks=self.hooks).validate(intent, draft)
        SchemaValidator(hooks=self.hooks).validate(draft)
        DeFiPayloadParser(self.config, hooks=self.hooks).validate(draft)
        self.hooks.invoke_hooks_isolated(
            HOOK_PRE_SIMULATION,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        rpc = RPCManager(self.config, hooks=self.hooks)
        block_number = rpc.sync_reconcile()
        w3 = rpc.sync_web3()
        sim = SandboxSimulator(hooks=self.hooks)
        so = cast(Optional[StateOverride], state_overrides)
        out = sim.simulate(
            draft,
            web3=w3,
            block_number=block_number,
            state_overrides=so,
        )
        ShadowAuditor().audit(
            payload=draft,
            simulation_result=out,
            security_policy=security_policy,
        )
        self.hooks.invoke_hooks_isolated(
            HOOK_POST_SIMULATION,
            intent=intent,
            payload=draft,
            simulation=out,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        self.hooks.invoke_hooks_isolated(
            HOOK_POST_VALIDATE,
            intent=intent,
            payload=draft,
            simulation=out,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        return {"validated": True, **out}

    async def async_validate_and_simulate(
        self,
        intent: str,
        payload: Mapping[str, Any],
        *,
        state_overrides: Optional[Dict[str, Any]] = None,
        security_policy: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """L1→L2→L3→L4→L5：异步路径（AsyncWeb3 + asyncio）。"""
        draft = dict(payload)
        await self.hooks.ainvoke_hooks_isolated(
            HOOK_PRE_VALIDATE,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        IntentValidator(self.config, hooks=self.hooks).validate(intent, draft)
        SchemaValidator(hooks=self.hooks).validate(draft)
        DeFiPayloadParser(self.config, hooks=self.hooks).validate(draft)
        await self.hooks.ainvoke_hooks_isolated(
            HOOK_PRE_SIMULATION,
            intent=intent,
            payload=draft,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        rpc = RPCManager(self.config, hooks=self.hooks)
        block_number = await rpc.async_reconcile()
        aw3 = rpc.async_web3()
        sim = SandboxSimulator(hooks=self.hooks)
        so = cast(Optional[StateOverride], state_overrides)
        out = await sim.simulate_async(
            draft,
            async_web3=aw3,
            block_number=block_number,
            state_overrides=so,
        )
        ShadowAuditor().audit(
            payload=draft,
            simulation_result=out,
            security_policy=security_policy,
        )
        await self.hooks.ainvoke_hooks_isolated(
            HOOK_POST_SIMULATION,
            intent=intent,
            payload=draft,
            simulation=out,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        await self.hooks.ainvoke_hooks_isolated(
            HOOK_POST_VALIDATE,
            intent=intent,
            payload=draft,
            simulation=out,
            timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
        )
        return {"validated": True, **out}


# Backward-compatible facade alias used in docs/integration examples.
Guardian = Lirix
