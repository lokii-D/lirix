"""Pattern: agent builds calldata; Lirix validates before any signing step."""

from __future__ import annotations

from typing import Any, Mapping

from lirix import Lirix, LirixConfig


def agent_build_payload(intent: str, user_request: Mapping[str, Any]) -> dict[str, Any]:
    """Placeholder: your agent turns user intent into router calldata."""
    _ = (intent, user_request)
    return {
        "to": "0x0000000000000000000000000000000000000000",
        "function_name": "swapExactTokensForTokens",
        "data": "0x",
    }


def run_guardrails(cfg: LirixConfig, intent: str, draft: Mapping[str, Any]) -> bool:
    """Call Lirix before exposing a transaction to a signer."""
    client = Lirix(cfg)
    return client.chain_validate(intent, draft)


def main() -> None:
    cfg = LirixConfig(
        chain_id=1,
        strict_mode=True,
        rpc_urls=[],
        allowed_intents=["swap"],
        allowed_function_names=["swapExactTokensForTokens"],
        allowed_to_addresses=[],
    )
    payload = agent_build_payload("swap", {})
    try:
        run_guardrails(cfg, "swap", payload)
    except Exception as exc:  # noqa: BLE001
        print("Validation failed as expected for placeholder payload:", type(exc).__name__, exc)


if __name__ == "__main__":
    main()
