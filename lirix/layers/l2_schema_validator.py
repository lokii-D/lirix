# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from web3 import Web3

from lirix.core.constants import HOOK_ISOLATED_TIMEOUT_SEC, HOOK_LAYER_L2
from lirix.core.exceptions import SchemaValidationException
from lirix.core.hook_manager import HookManager
from lirix.core.signatures import MAX_L2_CALLDATA_HEX_CHARS, UINT256_MAX


class _TxDraftSchema(BaseModel):
    """L2：Pydantic v2 强 schema，阻断幻觉地址、uint256 越界与超长 calldata。"""

    model_config = ConfigDict(extra="forbid", strict=False)

    to: str
    function_name: str = Field(..., min_length=1)
    value: int = Field(default=0, ge=0, le=UINT256_MAX)
    data: str = Field(default="0x", max_length=MAX_L2_CALLDATA_HEX_CHARS)
    assertions: list[dict[str, Any]] | None = None

    @field_validator("to", mode="after")
    @classmethod
    def _checksum_to(cls, v: str) -> str:
        if not Web3.is_address(v):
            raise ValueError("to is not a valid address")
        cs = Web3.to_checksum_address(v)
        if cs != v:
            raise ValueError("to must be EIP-55 checksum format")
        return cs

    @field_validator("data", mode="after")
    @classmethod
    def _hex_data(cls, v: str) -> str:
        if not isinstance(v, str) or not v.startswith("0x"):
            raise ValueError("data must be a 0x-prefixed hex string")
        body = v[2:]
        if len(body) % 2 != 0:
            raise ValueError("data hex length must be even")
        if body:
            bytes.fromhex(body)
        return v


class SchemaValidator:
    """L2：对交易草稿 dict 做 Pydantic 校验。"""

    def __init__(self, *, hooks: Optional[HookManager] = None) -> None:
        self._hooks = hooks

    def validate(self, payload: dict[str, Any]) -> bool:
        try:
            _TxDraftSchema.model_validate(payload)
        except PydanticValidationError as exc:
            raise SchemaValidationException(
                human_readable_reason="Payload failed schema validation.",
                context={"layer": "L2", "errors": exc.errors()},
            ) from exc
        h = self._hooks
        if h is not None:
            h.invoke_hooks_isolated(
                HOOK_LAYER_L2,
                layer="L2",
                payload=payload,
                timeout_sec=HOOK_ISOLATED_TIMEOUT_SEC,
            )
        return True

    def validate_mapping(self, payload: Mapping[str, Any]) -> bool:
        return self.validate(dict(payload))
