# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, List, Optional, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from web3 import Web3

from lirix.core.exceptions import ConfigurationGuardException


class LirixConfig(BaseModel):
    """全局配置基类（Pydantic v2）：初始化即完成地址 checksum 洗牌与边界校验。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chain_id: int = Field(..., ge=0, description="目标链 ID")
    rpc_urls: List[str] = Field(
        default_factory=list,
        description="RPC 端点列表（核心不得强绑定外网；断网场景由部署方提供本地 URL）",
    )
    allowed_intents: List[str] = Field(default_factory=list)
    strict_mode: bool = True
    blacklisted_addresses: List[str] = Field(default_factory=list)
    whitelisted_addresses: List[str] = Field(default_factory=list)
    allowed_function_names: List[str] = Field(
        default_factory=list,
        description="L1：允许出现在 payload.function_name 的函数名白名单",
    )
    allowed_to_addresses: List[str] = Field(
        default_factory=list,
        description="L1：允许作为外层 to 的合约地址白名单（checksum）",
    )
    multicall3_address: Optional[str] = Field(
        default=None,
        description="L3：Multicall3 地址；None 且 chain_id==1 时使用以太坊主网常量",
    )
    uniswap_v2_router: Optional[str] = Field(
        default=None,
        description="L3：Uniswap V2 Router；None 且 chain_id==1 时使用以太坊主网常量",
    )

    @field_validator("rpc_urls", mode="before")
    @classmethod
    def _normalize_rpc_urls(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ConfigurationGuardException(
                human_readable_reason="rpc_urls must be a list of strings.",
                context={
                    "field": "rpc_urls",
                    "reason": "type_invalid",
                    "value_type": type(v).__name__,
                },
            )
        out: List[str] = []
        for i, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ConfigurationGuardException(
                    human_readable_reason="Each rpc_urls entry must be a non-empty string.",
                    context={
                        "field": "rpc_urls",
                        "reason": "entry_invalid",
                        "index": i,
                        "value": item,
                    },
                )
            out.append(item.strip())
        return out

    @field_validator("allowed_intents", mode="before")
    @classmethod
    def _normalize_intents(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ConfigurationGuardException(
                human_readable_reason="allowed_intents must be a list of strings.",
                context={
                    "field": "allowed_intents",
                    "reason": "type_invalid",
                    "value_type": type(v).__name__,
                },
            )
        out: List[str] = []
        for i, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ConfigurationGuardException(
                    human_readable_reason="Each allowed_intents entry must be a non-empty string.",
                    context={
                        "field": "allowed_intents",
                        "reason": "entry_invalid",
                        "index": i,
                        "value": item,
                    },
                )
            out.append(item.strip())
        return out

    @field_validator("allowed_function_names", mode="before")
    @classmethod
    def _normalize_function_names(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ConfigurationGuardException(
                human_readable_reason="allowed_function_names must be a list of strings.",
                context={
                    "field": "allowed_function_names",
                    "reason": "type_invalid",
                    "value_type": type(v).__name__,
                },
            )
        out: List[str] = []
        for i, item in enumerate(v):
            if not isinstance(item, str) or not item.strip():
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "Each allowed_function_names entry must be a non-empty string."
                    ),
                    context={
                        "field": "allowed_function_names",
                        "reason": "entry_invalid",
                        "index": i,
                        "value": item,
                    },
                )
            out.append(item.strip())
        return out

    @field_validator("multicall3_address", "uniswap_v2_router", mode="before")
    @classmethod
    def _optional_contract_address(cls, v: Any, info: ValidationInfo) -> Optional[str]:
        field_name = str(info.field_name or "contract_address")
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        if not isinstance(v, str):
            raise ConfigurationGuardException(
                human_readable_reason=f"{field_name} must be a string address or empty.",
                context={
                    "field": field_name,
                    "reason": "type_invalid",
                    "value_type": type(v).__name__,
                },
            )
        raw = v.strip()
        if not Web3.is_address(raw):
            raise ConfigurationGuardException(
                human_readable_reason=f"{field_name} is not a valid hex address.",
                context={"field": field_name, "reason": "address_invalid", "value": raw},
            )
        return Web3.to_checksum_address(raw)

    @field_validator(
        "blacklisted_addresses",
        "whitelisted_addresses",
        "allowed_to_addresses",
        mode="before",
    )
    @classmethod
    def _normalize_address_list(cls, v: Any, info: ValidationInfo) -> List[str]:
        field_name = str(info.field_name or "addresses")
        if v is None:
            return []
        if not isinstance(v, Sequence) or isinstance(v, (str, bytes)):
            raise ValueError(f"{field_name} must be a list of address strings.")
        out: List[str] = []
        for i, item in enumerate(v):
            if not isinstance(item, str):
                raise ValueError(f"{field_name}[{i}] must be a non-empty string address.")
            raw = item.strip()
            if not raw:
                raise ValueError(f"{field_name}[{i}] must be a non-empty string address.")
            if not Web3.is_address(raw):
                raise ValueError(f"{field_name}[{i}] is not a valid hex address.")
            out.append(Web3.to_checksum_address(raw))
        return out

    @model_validator(mode="after")
    def _guard_lists(self) -> LirixConfig:
        if self.strict_mode:
            overlap = set(self.blacklisted_addresses) & set(self.whitelisted_addresses)
            if overlap:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "strict_mode forbids overlapping blacklist and whitelist."
                    ),
                    context={"reason": "overlap_blacklist_whitelist", "overlap": sorted(overlap)},
                )
            bad_to = set(self.blacklisted_addresses) & set(self.allowed_to_addresses)
            if bad_to:
                raise ConfigurationGuardException(
                    human_readable_reason=(
                        "strict_mode forbids addresses in both blacklisted_addresses "
                        "and allowed_to_addresses."
                    ),
                    context={"reason": "overlap_blacklist_allowed_to", "overlap": sorted(bad_to)},
                )
        return self
