from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import LirixSecurityException
from lirix.layers.l5_shadow_auditor import ShadowPolicySchema


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


st.set_page_config(page_title="Lirix · Mantle Demo", page_icon="🛡️", layout="wide")
st.title("Lirix on Mantle")
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
    st.write("Env override", "MANTLE_RPC_URLS" if os.getenv("MANTLE_RPC_URLS") else "MANTLE_MAINNET_RPC / preset")

st.info(
    "This demo intentionally avoids fabricating transaction hashes or explorer links. "
    "It only shows real validation results."
)

st.subheader("Payload")
example = {
    "to": "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
    "function_name": "swap",
    "value": 0,
    "data": "0xd004f0f8" + "00" * 32 * 5,
}
raw = st.text_area("Enter JSON payload", value=json.dumps(example, indent=2), height=240)
intent = st.text_input("Intent", value="swap")

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
        except LirixSecurityException as exc:
            pipeline_state.append(("L1-L3", "blocked", f"Blocked: {exc}"))
            pipeline_state.append(("L4", "skipped", "Skipped because validation failed before RPC quorum."))
            pipeline_state.append(("L5", "skipped", "Skipped because validation failed before simulation."))
            pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))
        else:
            try:
                sim = client.validate_and_simulate(intent, payload, security_policy=policy)
                pipeline_state.append(("L4", "passed", "RPC quorum and reconciliation completed."))
                pipeline_state.append(("L5", "passed", f"Simulation returned: {sim.get('status', 'ok')}"))
                pipeline_state.append(("Decision", "passed", "Safe to proceed."))
            except LirixSecurityException as exc:
                pipeline_state.append(("L4/L5", "blocked", f"Simulation blocked: {exc}"))
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))

        st.subheader("L1–L5 Status")
        for label, state, detail in pipeline_state:
            _status_row(label, state, detail)

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

        st.subheader("Explorer")
        tx_hash = payload.get("tx_hash")
        if isinstance(tx_hash, str) and tx_hash.startswith("0x") and len(tx_hash) == 66:
            try:
                int(tx_hash, 16)
            except ValueError:
                st.info("Mantle Explorer transaction links appear only when a real on-chain tx_hash is supplied.")
            else:
                explorer_base = "https://explorer.mantle.xyz/tx"
                st.markdown(f"[Mantle Explorer transaction link]({explorer_base}/{tx_hash})")
        else:
            st.info("Mantle Explorer transaction links appear only when a real on-chain tx_hash is supplied.")

        st.subheader("Raw Result")
        st.json({"network": network_name, "chain_id": config.chain_id, "intent": intent, "payload": payload})

        if pipeline_state and pipeline_state[-1][0] == "Decision":
            final = pipeline_state[-1][1]
            if final == "passed":
                st.success("Final decision: safe")
            else:
                st.error("Final decision: blocked")

    except (json.JSONDecodeError, ValueError) as exc:
        st.error(f"Invalid payload JSON: {exc}")
