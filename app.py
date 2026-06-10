from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st
from eth_abi import encode as eth_abi_encode
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import LirixBaseException, LirixSecurityException
from lirix.layers.l5_shadow_auditor import ShadowPolicySchema
from web3 import Web3


def _env_rpc_urls() -> list[str] | None:
    raw = os.getenv("MANTLE_RPC_URLS") or os.getenv("MANTLE_MAINNET_RPC")
    if not raw:
        return None
    urls = [item.strip() for item in raw.split(",") if item.strip()]
    return urls or None


def _build_config(testnet: bool) -> LirixConfig:
    base = LirixConfig.for_mantle(testnet=testnet)
    env_urls = _env_rpc_urls()
    if env_urls:
        return base.model_copy(update={"rpc_urls": env_urls})
    return base


def _status_row(label: str, state: str, detail: str) -> None:
    left, right = st.columns([1, 4])
    with left:
        if state == "passed":
            st.success(label)
        elif state == "blocked":
            st.error(label)
        elif state == "skipped":
            st.info(label)
        else:
            st.warning(label)
    with right:
        st.write(detail)


def _build_v2_swap_payload(amount_out_min: int, *, amount_in: int = 1) -> dict[str, Any]:
    router = "0xeaEE7EE68874218c3558b40063c42B82D3E7232a"
    path = [
        Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    ]
    data = eth_abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [amount_in, amount_out_min, path, router, 0],
    )
    return {
        "to": router,
        "function_name": "swapExactTokensForTokens",
        "value": 0,
        "data": "0x38ed1739" + data.hex(),
    }


def _build_moe_swap_payload(amount_out_min: int, *, amount_in: int = 1) -> dict[str, Any]:
    router = "0xeaEE7EE68874218c3558b40063c42B82D3E7232a"
    path = [
        Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    ]
    data = eth_abi_encode(
        ["uint256", "uint256", "address[]", "address", "uint256"],
        [amount_in, amount_out_min, path, router, 0],
    )
    return {
        "to": router,
        "function_name": "swap",
        "value": 0,
        "data": "0xd004f0f8" + data.hex(),
    }


def _build_v3_swap_payload(amount_in: int, amount_out_min: int) -> dict[str, Any]:
    router = "0xeaEE7EE68874218c3558b40063c42B82D3E7232a"
    v3_path = bytes.fromhex(
        "A0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        + "000bb8"
        + "C02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    )
    data = eth_abi_encode(
        ["bytes", "address", "uint256", "uint256", "uint256", "bytes"],
        [v3_path, router, amount_in, amount_out_min, 0, b""],
    )
    return {
        "to": router,
        "function_name": "exactInput",
        "value": 0,
        "data": "0x"
        + Web3.keccak(text="exactInput((bytes,address,uint256,uint256,uint256,bytes))")[:4].hex()
        + data.hex(),
    }


st.set_page_config(page_title="Lirix · Mantle Demo", page_icon="🛡️", layout="wide")
st.title("Lirix on Mantle")
st.markdown(
    """
<div style="background: linear-gradient(90deg, #1e3a8a, #3b82f6);
    color: white; padding: 16px; border-radius: 12px; text-align: center;
    margin-bottom: 20px;">
    <h2>🛡️ Lirix 2.0.4 – Mantle AI Agent 安全守护者</h2>
    <p><strong>fail-closed 分层安全管线</strong> · L1–L5 线性 DAG ·
    SHA-256 证据链 · Mantle Native</p>
</div>
""",
    unsafe_allow_html=True,
)
st.caption("Layered AI DevTools security demo for Mantle transactions")

with st.sidebar:
    st.header("Network")
    network_name = st.selectbox("Select Mantle network", ["Mantle Mainnet", "Mantle Testnet"])
    testnet = network_name == "Mantle Testnet"
    config = _build_config(testnet)
    st.write("Chain ID", config.chain_id)
    st.write("RPC URLs", len(config.rpc_urls))
    st.write("Multicall3", config.multicall3_address)
    st.write("Router", config.uniswap_v2_router)
    st.divider()
    st.write(
        "Env override",
        "MANTLE_RPC_URLS" if os.getenv("MANTLE_RPC_URLS") else "MANTLE_MAINNET_RPC / preset",
    )

st.info(
    "This demo intentionally avoids fabricating transaction hashes or explorer links. "
    "It only shows real validation results."
)

st.subheader("🚀 Quick Test Scenarios")
if "payload_text" not in st.session_state:
    st.session_state["payload_text"] = json.dumps(
        _build_v2_swap_payload(amount_out_min=1), indent=2
    )
if "intent_text" not in st.session_state:
    st.session_state["intent_text"] = "swap"
col1, col2, col3 = st.columns(3)
with col1:
    if st.button(
        "🚫 恶意示例（Merchant Moe 路由毒化）", use_container_width=True, type="secondary"
    ):
        st.session_state["payload_text"] = json.dumps(
            _build_moe_swap_payload(amount_out_min=0), indent=2
        )
        st.session_state["intent_text"] = "swap"
with col2:
    if st.button("✅ 安全 Swap 示例", use_container_width=True, type="primary"):
        st.session_state["payload_text"] = json.dumps(
            _build_v2_swap_payload(amount_out_min=1), indent=2
        )
        st.session_state["intent_text"] = "swap"
with col3:
    if st.button("🔄 Self-repair 修复示例", use_container_width=True):
        st.session_state["payload_text"] = json.dumps(
            _build_v3_swap_payload(amount_in=1, amount_out_min=1), indent=2
        )
        st.session_state["intent_text"] = "swap"
raw = st.text_area("Enter JSON payload", key="payload_text", height=240)
intent = st.text_input("Intent", key="intent_text")

st.caption("Tip: add a real `tx_hash` key to the JSON to render the Mantle Explorer link.")
policy = ShadowPolicySchema(
    max_slippage_bps=50,
    forbidden_methods=["approve"],
    allowed_target_contracts="ANY",
)

col1, col2 = st.columns(2)
with col1:
    run_validate = st.button("Run L1-L5 pipeline", type="primary")
with col2:
    st.write("L4/L5 will run only when RPC endpoints are provided and reachable.")

if run_validate:
    try:
        payload: dict[str, Any] = json.loads(raw)
        client = Lirix(config)
        pipeline_state: list[tuple[str, str, str]] = []

        try:
            client.chain_validate(intent, payload)
            pipeline_state.append(("L1", "passed", "Intent allowed and payload accepted."))
            pipeline_state.append(("L2", "passed", "Schema validation passed."))
            pipeline_state.append(("L3", "passed", "DeFi parser and whitelist checks passed."))
        except LirixBaseException as exc:
            if isinstance(exc, LirixSecurityException):
                st.error("🚫 BLOCKED by Lirix Security Pipeline")
                st.info(f"**Layer**: {exc.__class__.__name__}\n**Reason**: {str(exc)}")
                st.caption(
                    "✅ This is Lirix fail-closed protection in action. "
                    "The payload was prevented from reaching Mantle."
                )
                pipeline_state.append(("L1-L3", "blocked", f"Blocked: {exc}"))
                pipeline_state.append(
                    ("L4", "skipped", "Skipped because validation failed before RPC quorum.")
                )
                pipeline_state.append(
                    ("L5", "skipped", "Skipped because validation failed before simulation.")
                )
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))
            else:
                st.error(f"🚫 Lirix runtime issue: {exc.__class__.__name__}")
                st.info(f"**Reason**: {str(exc)}")
                st.caption("Please refresh the demo or check the Mantle RPC configuration.")
                pipeline_state.append(("L1-L3", "blocked", exc.__class__.__name__))
                pipeline_state.append(("L4", "skipped", "Skipped because runtime setup failed."))
                pipeline_state.append(("L5", "skipped", "Skipped because runtime setup failed."))
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))
        else:
            try:
                sim = client.validate_and_simulate(intent, payload, security_policy=policy)
                pipeline_state.append(("L4", "passed", "RPC quorum and reconciliation completed."))
                pipeline_state.append(
                    ("L5", "passed", f"Simulation returned: {sim.get('status', 'ok')}")
                )
                pipeline_state.append(("Decision", "passed", "Safe to proceed."))
            except LirixBaseException as exc:
                st.error("🚫 BLOCKED by Lirix Security Pipeline")
                st.info(f"**Layer**: {exc.__class__.__name__}\n**Reason**: {str(exc)}")
                st.caption(
                    "✅ This is Lirix fail-closed protection in action. "
                    "The payload was prevented from reaching Mantle."
                )
                pipeline_state.append(("L4/L5", "blocked", f"Simulation blocked: {exc}"))
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))

        st.subheader("🔄 L1–L5 Security Pipeline")
        progress_cols = st.columns(len(pipeline_state))
        for i, (label, state, detail) in enumerate(pipeline_state):
            with progress_cols[i]:
                if state == "passed":
                    st.success(f"**{label}** ✓")
                elif state == "blocked":
                    st.error(f"**{label}** ✗")
                else:
                    st.info(f"**{label}**")
                st.caption(detail)

        st.subheader("ShadowAuditor")
        shadow_cols = st.columns(3)
        shadow_cols[0].metric("Max slippage", f"{policy.max_slippage_bps} bps")
        shadow_cols[1].metric("Forbidden methods", len(policy.forbidden_methods))
        shadow_cols[2].metric("Allowed targets", policy.allowed_target_contracts)
        st.json(
            {
                "max_slippage_bps": policy.max_slippage_bps,
                "forbidden_methods": policy.forbidden_methods,
                "allowed_target_contracts": policy.allowed_target_contracts,
            }
        )

        st.subheader("🛡️ Lirix 2.0.4 Core Strengths")
        cols = st.columns(4)
        cols[0].metric("Config", "Frozen", "Immutable governance")
        cols[1].metric("Orchestrator", "Linear DAG", "L1→L5 fail-closed")
        cols[2].metric("Evidence", "SHA-256", "Tamper-proof replay")
        cols[3].metric("Failure Protocol", "Agent-ready", "Self-healing ready")

        st.subheader("🛡️ How Lirix Protects Mantle AI Agents")
        st.markdown(
            """
- **L1-L3**：意图 + Schema + DeFi calldata 解析（Merchant Moe / Agni / Pendle 支持）
- **L4**：RPC Quorum + block height spread fail-closed
- **L5**：零 Gas 模拟 + Shadow Auditor 策略裁决
- **Evidence**：SHA-256 replay digest + structured Failure Protocol（Agent self-healing ready）
"""
        )

        st.subheader("Explorer")
        tx_hash = payload.get("tx_hash")
        if isinstance(tx_hash, str) and tx_hash.startswith("0x") and len(tx_hash) == 66:
            try:
                int(tx_hash, 16)
            except ValueError:
                st.info(
                    "Mantle Explorer transaction links appear only when a real on-chain "
                    "tx_hash is supplied."
                )
            else:
                explorer_base = "https://explorer.mantle.xyz/tx"
                st.markdown(f"[Mantle Explorer transaction link]({explorer_base}/{tx_hash})")
        else:
            st.info(
                "Mantle Explorer transaction links appear only when a real on-chain "
                "tx_hash is supplied."
            )

        st.subheader("Raw Result")
        st.json(
            {
                "network": network_name,
                "chain_id": config.chain_id,
                "intent": intent,
                "payload": payload,
            }
        )

        if pipeline_state and pipeline_state[-1][0] == "Decision":
            final = pipeline_state[-1][1]
            if final == "passed":
                st.success("🎉 FINAL DECISION: SAFE TO EXECUTE ON MANTLE")
                st.balloons()
            else:
                st.error("🚫 FINAL DECISION: BLOCKED (fail-closed protection activated)")
                st.caption(
                    "Lirix 2.0.4 successfully prevented a potential malicious "
                    "transaction on Mantle."
                )

        st.caption("📌 Lirix always returns structured Failure Protocol for AI Agent self-healing.")

    except (json.JSONDecodeError, ValueError) as exc:
        st.error(f"Invalid payload JSON: {exc}")

st.divider()
st.caption("🔥 Built for Mantle Turing Test Hackathon 2026 · Lirix 2.0.4 · fail-closed by design")
