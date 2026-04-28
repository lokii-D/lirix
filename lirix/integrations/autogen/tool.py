# SPDX-License-Identifier: MIT
from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence, cast

from lirix import Lirix
from lirix.core.exceptions import LirixBaseException
from lirix.integrations.langchain.tool import _format_security_exception


def lirix_validate_intent(
    raw_intent_or_calldata: str,
    rpc_urls: Sequence[str],
    intent: Optional[str] = None,
    state_delta_assertions: Optional[Mapping[str, Any]] = None,
    security_policy: Optional[Mapping[str, Any]] = None,
) -> str:
    """Validate untrusted agent output through Lirix for AutoGen function calling.

    This function is intentionally standalone so it can be registered with
    AutoGen's `register_for_llm` and `register_for_execution` protocols.

    Args:
        raw_intent_or_calldata: The raw intent, calldata, or generated payload
            that must be validated before any chain interaction.
        rpc_urls: Ordered RPC endpoints used by Lirix to reconcile state.
        intent: Optional execution label such as `swap`, `transfer`, or
            `contract_call`.
        state_delta_assertions: Optional L5 state-delta expectations, including
            assertions such as `assert_erc20_balance_increase`.

    Returns:
        A JSON-like string for safe results, or the remediation string from
        `LirixSecurityException.resolution_for_agent` when the payload is unsafe.
    """
    guardian = Lirix(rpc_urls=rpc_urls)
    merged_payload = {"raw_intent_or_calldata": raw_intent_or_calldata}
    if state_delta_assertions is not None:
        merged_payload.update(dict(state_delta_assertions))
    resolved_intent = intent or "unknown"
    try:
        result = guardian.validate_and_simulate(
            resolved_intent,
            merged_payload,
            security_policy=dict(security_policy) if security_policy is not None else None,
        )
    except LirixBaseException as exc:
        return _format_security_exception(exc)
    if hasattr(result, "model_dump_json"):
        return str(cast(Any, result).model_dump_json())
    return str(result)
