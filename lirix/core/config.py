# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, ClassVar, List, Optional, Sequence

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

MANTLE_MAINNET_RPC_URLS: tuple[str, ...] = (
    "https://rpc.mantle.xyz",
    "https://mantle.drpc.org",
    "https://rpc.ankr.com/mantle",
)
MANTLE_TESTNET_RPC_URLS: tuple[str, ...] = ("https://rpc.testnet.mantle.xyz",)
MANTLE_CHAIN_ID: int = 5000
MANTLE_TESTNET_CHAIN_ID: int = 5001
MANTLE_ALLOWED_TO_ADDRESSES: frozenset[str] = frozenset(
    {
        # DEX Routers
        "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",  # Merchant Moe MoeRouter
        "0x6e3d7b0365c960aaf214e0afa86a99b4a62ae82d",  # Agni Finance Swap Router
        # Yield/Lending protocols
        "0x888888888889758F76e7103c6CbF23ABbF58F946",  # Pendle Router V4
        "0x972BcB0284cca0152527c4f70f8F689852bCAFc5",  # INIT Capital InitCore (Proxy)
        # Asset tokens
        "0xcDA86A272531e8640cD7F1a92c01839911B90bb0",  # mETH
        "0xE6829d9a7eE3040e1276Fa75293Bde931859e8fA",  # cmETH
        "0xC96dE26018A54D51c097160568752c4E3BD6C364",  # FBTC
        "0x5bE26527e817998A7206475496fDE1E68957c5A6",  # USDY
        "0x78c1b0C915c4FAA5FFfA6CAbf0219DA63d7f4cb8",  # WMNT
        "0x4515a45337f461a11ff0fe8abf3c606ae5dc00c9",  # MOE
    }
)


class LirixConfig(BaseModel):
    """全局配置基类（Pydantic v2）：初始化即完成地址 checksum 洗牌与边界校验。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    MANTLE_MAINNET_RPC_URLS: ClassVar[tuple[str, ...]] = MANTLE_MAINNET_RPC_URLS
    MANTLE_TESTNET_RPC_URLS: ClassVar[tuple[str, ...]] = MANTLE_TESTNET_RPC_URLS
    MANTLE_CHAIN_ID: ClassVar[int] = MANTLE_CHAIN_ID
    MANTLE_TESTNET_CHAIN_ID: ClassVar[int] = MANTLE_TESTNET_CHAIN_ID
    MANTLE_ALLOWED_TO_ADDRESSES: ClassVar[frozenset[str]] = MANTLE_ALLOWED_TO_ADDRESSES

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

    @staticmethod
    def for_mantle(*, testnet: bool = False, strict_mode: bool = True) -> LirixConfig:
        chain_id = MANTLE_TESTNET_CHAIN_ID if testnet else MANTLE_CHAIN_ID
        rpc_urls = list(MANTLE_TESTNET_RPC_URLS if testnet else MANTLE_MAINNET_RPC_URLS)
        whitelisted = sorted(
            set(MANTLE_ALLOWED_TO_ADDRESSES)
            | {
                "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "0xcA11bde05977b3631167028862bE2a173976CA11",
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955",
                "0x000000000000000000000000000000000000dEaD",
            }
        )
        return LirixConfig(
            chain_id=chain_id,
            rpc_urls=rpc_urls,
            strict_mode=strict_mode,
            allowed_intents=["swap", "transfer", "bridge", "simulate"],
            allowed_function_names=[
                "swap",
                "swapExactTokensForTokens",
                "swapExactETHForTokens",
                "swapExactTokensForETH",
                "exactInput",
                "exactOutput",
            ],
            allowed_to_addresses=list(MANTLE_ALLOWED_TO_ADDRESSES),
            whitelisted_addresses=whitelisted,
            blacklisted_addresses=["0x000000000000000000000000000000000000bEEF"],
            multicall3_address="0xcA11bde05977b3631167028862bE2a173976CA11",
            uniswap_v2_router="0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
        )
