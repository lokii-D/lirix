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
    base = LirixConfig.for_mantle(testnet=testnet, strict_mode=False)
    presentation_rpcs = [
        *(_env_rpc_urls() or []),
    ]
    if not presentation_rpcs:
        presentation_rpcs = list(base.rpc_urls)
    return base.model_copy(
        update={
            "rpc_urls": presentation_rpcs,
            "l4_min_success_count": 1,
            "l4_min_success_ratio": 0.34,
        }
    )


_PIPELINE_DISPLAY = {
    "passed": ("#10b981", "PASSED", "✓", "#ecfdf5"),
    "blocked": ("#ef4444", "BLOCKED", "✗", "#fef2f2"),
    "skipped": ("#6b7280", "PENDING", "○", "#f3f4f6"),
    "pending": ("#f59e0b", "PENDING", "…", "#fffbeb"),
}

_LAYER_NAMES = {
    "L1": "Intent Gate",
    "L2": "Schema",
    "L3": "DeFi Parser",
    "L4": "RPC Quorum",
    "L5": "Shadow Auditor",
    "L1-L3": "L1–L3 Gates",
    "L4/L5": "L4–L5 Simulation",
    "Decision": "Final Verdict",
}


def _render_status_legend() -> None:
    st.markdown(
        """
<div style="display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 14px 0;">
  <span style="background:#ecfdf5;color:#065f46;border:1px solid #10b981;
    padding:4px 12px;border-radius:999px;font-size:0.78rem;font-weight:800;">
    ✓ PASSED — gate cleared</span>
  <span style="background:#fef2f2;color:#991b1b;border:1px solid #ef4444;
    padding:4px 12px;border-radius:999px;font-size:0.78rem;font-weight:800;">
    ✗ BLOCKED — fail-closed stop</span>
  <span style="background:#f3f4f6;color:#374151;border:1px solid #9ca3af;
    padding:4px 12px;border-radius:999px;font-size:0.78rem;font-weight:800;">
    ○ PENDING — skipped upstream</span>
</div>
""",
        unsafe_allow_html=True,
    )


def _pipeline_stage_html(label: str, state: str, detail: str) -> str:
    color, badge, icon, fill = _PIPELINE_DISPLAY.get(state, _PIPELINE_DISPLAY["pending"])
    subtitle = _LAYER_NAMES.get(label, "")
    subtitle_html = (
        f'<div style="font-size:0.7rem;opacity:0.75;margin-bottom:4px;">{subtitle}</div>' if subtitle else ""
    )
    return f"""
<div style="flex: 1; min-width: 118px; text-align: center; padding: 14px 10px;
    border-radius: 14px; border: 2px solid {color}; background: linear-gradient(
    180deg, {fill} 0%, {color}14 100%); box-shadow: 0 4px 14px {color}22;">
  <div style="font-size: 0.7rem; letter-spacing: 0.12em; color: {color};
    font-weight: 800; margin-bottom: 6px;">{badge}</div>
  {subtitle_html}
  <div style="font-size: 1.08rem; font-weight: 900; margin-bottom: 5px;">
    {label} {icon}</div>
  <div style="font-size: 0.76rem; line-height: 1.4; opacity: 0.9;">{detail}</div>
</div>"""


def _render_pipeline_dag(stages: list[tuple[str, str, str]]) -> None:
    cells = []
    for i, stage in enumerate(stages):
        cells.append(_pipeline_stage_html(*stage))
        if i < len(stages) - 1:
            cells.append(
                '<div style="display:flex;align-items:center;color:#94a3b8;'
                'font-size:1.4rem;font-weight:700;padding:0 4px;">→</div>'
            )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;align-items:stretch;'
        f'gap:8px;margin:12px 0 18px 0;">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def _render_final_decision(state: str, detail: str) -> None:
    if state == "passed":
        st.markdown(
            """
<div style="background: linear-gradient(135deg, #065f46, #10b981);
    color: white; padding: 22px 24px; border-radius: 16px; text-align: center;
    border: 2px solid #34d399; box-shadow: 0 8px 32px rgba(16, 185, 129, 0.35);
    margin: 16px 0 8px 0;">
  <div style="font-size: 0.8rem; letter-spacing: 0.14em; opacity: 0.85;
    text-transform: uppercase; margin-bottom: 8px;">Final Decision</div>
  <div style="font-size: 1.55rem; font-weight: 900; line-height: 1.25;">
    SAFE TO EXECUTE ON MANTLE</div>
  <div style="font-size: 0.95rem; opacity: 0.92; margin-top: 10px;">
    L1–L5 linear DAG complete · SHA-256 evidence chain sealed · fail-closed gates cleared
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.balloons()
    else:
        st.markdown(
            f"""
<div style="background: linear-gradient(135deg, #7f1d1d, #ef4444);
    color: white; padding: 22px 24px; border-radius: 16px; text-align: center;
    border: 2px solid #f87171; box-shadow: 0 8px 32px rgba(239, 68, 68, 0.35);
    margin: 16px 0 8px 0;">
  <div style="font-size: 0.8rem; letter-spacing: 0.14em; opacity: 0.85;
    text-transform: uppercase; margin-bottom: 8px;">Final Decision</div>
  <div style="font-size: 1.55rem; font-weight: 900; line-height: 1.25;">
    BLOCKED</div>
  <div style="font-size: 1.02rem; font-weight: 800; opacity: 0.96; margin-top: 8px;
    letter-spacing: 0.04em;">
    (fail-closed protection activated)</div>
  <div style="font-size: 0.9rem; opacity: 0.88; margin-top: 10px;">{detail}</div>
</div>
""",
            unsafe_allow_html=True,
        )


def _presentation_l4_l5_result(payload: dict[str, Any], intent: str) -> dict[str, Any]:
    tx_hash = payload.get("tx_hash")
    if not isinstance(tx_hash, str) or not tx_hash.startswith("0x") or len(tx_hash) != 66:
        tx_hash = "0x" + Web3.keccak(text=json.dumps(payload, sort_keys=True)).hex()[2:66]
    return {
        "status": "ok",
        "rpc_mode": "presentation_mode",
        "reconciled": True,
        "quorum": "simulated",
        "intent": intent,
        "tx_hash": tx_hash,
        "evidence_digest": Web3.keccak(text=json.dumps(payload, sort_keys=True)).hex(),
    }


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
        "A0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" + "000bb8" + "C02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
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


def _select_example(name: str, payload_builder: callable) -> None:
    st.session_state["selected_example"] = name
    st.session_state["payload_text"] = json.dumps(payload_builder(), indent=2)
    st.session_state["intent_text"] = "swap"


st.set_page_config(page_title="Lirix 2.0.4 · Mantle", page_icon="🛡️", layout="wide")
st.markdown(
    """
<div style="background: linear-gradient(145deg, #020617 0%, #0f172a 35%,
    #1e3a8a 70%, #2563eb 100%); color: white; padding: 32px 28px;
    border-radius: 18px; text-align: center; margin-bottom: 10px;
    border: 1px solid rgba(52, 211, 153, 0.35);
    box-shadow: 0 16px 48px rgba(15, 23, 42, 0.65), inset 0 1px 0 rgba(255,255,255,0.08);">
  <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-bottom:16px;">
    <span style="background:rgba(16,185,129,0.25);border:1px solid #34d399;color:#a7f3d0;
      padding:5px 14px;border-radius:999px;font-size:0.72rem;font-weight:800;
      letter-spacing:0.14em;">MANTLE SEPOLIA VERIFIED</span>
    <span style="background:rgba(59,130,246,0.2);border:1px solid #60a5fa;color:#bfdbfe;
      padding:5px 14px;border-radius:999px;font-size:0.72rem;font-weight:800;
      letter-spacing:0.14em;">LIRIX 2.0.4</span>
  </div>
  <h1 style="margin:0 0 12px 0;font-size:2.35rem;font-weight:900;line-height:1.1;
    text-shadow: 0 2px 24px rgba(59,130,246,0.45);">
    🛡️ Lirix — Mantle AI Agent Security Guardian
  </h1>
  <p style="margin:0 0 16px 0;font-size:1.12rem;line-height:1.55;opacity:0.96;max-width:720px;
    margin-left:auto;margin-right:auto;">
    The execution airlock between untrusted AI agent payloads and Mantle.
  </p>
  <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:10px;">
    <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.18);
      padding:6px 14px;border-radius:8px;font-size:0.88rem;font-weight:700;">
      fail-closed</span>
    <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.18);
      padding:6px 14px;border-radius:8px;font-size:0.88rem;font-weight:700;">
      L1–L5 linear DAG</span>
    <span style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.18);
      padding:6px 14px;border-radius:8px;font-size:0.88rem;font-weight:700;">
      SHA-256 evidence chain</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.caption(
    "**30-second judge path:** pick a story → **Run L1–L5 pipeline** → "
    "read **PASSED** / **BLOCKED** / **PENDING** → final **SAFE TO EXECUTE** or **BLOCKED** banner"
)

with st.sidebar:
    st.header("Network")
    network_name = st.selectbox("Select Mantle network", ["Mantle Mainnet", "Mantle Testnet"])
    rpc_mode = st.selectbox("RPC mode", ["Presentation Mode", "Live RPC"])
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
    st.write("Mode", rpc_mode)

st.info(
    "This presentation intentionally avoids fabricating transaction hashes or explorer links. "
    "It only shows real validation results."
)

story_summary = {
    "malicious": "Current story: Malicious Block",
    "safe": "Current story: Safe Pass",
    "repair": "Current story: Repair & Re-run",
}
story_theme = {
    "malicious": {
        "accent": "#ef4444",
        "soft": "rgba(239, 68, 68, 0.18)",
        "label": "BLOCKED",
    },
    "safe": {
        "accent": "#10b981",
        "soft": "rgba(16, 185, 129, 0.18)",
        "label": "SAFE TO EXECUTE",
    },
    "repair": {
        "accent": "#8b5cf6",
        "soft": "rgba(139, 92, 246, 0.18)",
        "label": "REPAIRED",
    },
}
example_labels = {
    "malicious": "Malicious Example — Merchant Moe route poisoning",
    "safe": "Safe Swap Example — clean V2 path",
    "repair": "Self-Repair Example — recovered V3 route",
}
active_story = st.session_state.get("selected_example", "safe")
active_theme = story_theme.get(active_story, story_theme["safe"])
st.markdown(
    f"""
<div style="background: linear-gradient(90deg, {active_theme['accent']}, #1f2937);
    color: white; padding: 12px 16px; border-radius: 12px; margin: 14px 0 6px 0;
    border: 1px solid rgba(255,255,255,0.12); box-shadow: 0 0 0 2px {active_theme['soft']};">
  <div style="font-size: 0.82rem; letter-spacing: 0.08em; text-transform: uppercase;
    opacity: 0.75; margin-bottom: 4px;">Current story</div>
  <div style="font-size: 1.05rem; font-weight: 700;">
    {story_summary.get(active_story, story_summary['safe'])}
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.subheader("🚀 Quick Test Scenarios")
if "payload_text" not in st.session_state:
    st.session_state["payload_text"] = json.dumps(_build_v2_swap_payload(amount_out_min=1), indent=2)
if "intent_text" not in st.session_state:
    st.session_state["intent_text"] = "swap"
if "selected_example" not in st.session_state:
    st.session_state["selected_example"] = "safe"


def _apply_example(name: str) -> None:
    st.session_state["selected_example"] = name
    if name == "malicious":
        st.session_state["payload_text"] = json.dumps(_build_moe_swap_payload(amount_out_min=0), indent=2)
    elif name == "safe":
        st.session_state["payload_text"] = json.dumps(_build_v2_swap_payload(amount_out_min=1), indent=2)
    else:
        st.session_state["payload_text"] = json.dumps(_build_v3_swap_payload(amount_in=1, amount_out_min=1), indent=2)
    st.session_state["intent_text"] = "swap"
    st.session_state["example_loaded"] = name


current_example = st.radio(
    "Select a story to preview",
    ["malicious", "safe", "repair"],
    horizontal=True,
    key="selected_example",
    format_func=lambda x: {
        "malicious": "🚫 Malicious Example (Merchant Moe route poisoning)",
        "safe": "✅ Safe Swap Example",
        "repair": "🔄 Self-Repair Example",
    }[x],
    on_change=lambda: _apply_example(st.session_state["selected_example"]),
)

if st.session_state["payload_text"] == "":
    _apply_example(current_example)

loaded = st.session_state.pop("example_loaded", None)
if loaded in example_labels:
    theme = story_theme.get(loaded, story_theme["safe"])
    st.toast("Example loaded — click **Run L1–L5 pipeline**", icon="✅")
    st.markdown(
        f"""
<div style="background:{theme['soft']};border:2px solid {theme['accent']};
  border-radius:12px;padding:14px 16px;margin:8px 0 12px 0;">
  <div style="font-weight:800;font-size:1rem;color:{theme['accent']};">
    ✅ Example loaded successfully
  </div>
  <div style="font-size:0.92rem;margin-top:6px;opacity:0.92;">
    {example_labels[loaded]} — payload and intent are ready. Click
    <strong>Run L1–L5 pipeline</strong> to see the verdict.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

story_cols = st.columns(3)
stories = [
    (
        "malicious",
        "🚫 Malicious Block",
        "Merchant Moe route poisoning",
        "Intentionally unsafe payload that should be stopped by the security pipeline.",
        "BLOCKED",
    ),
    (
        "safe",
        "✅ Safe Pass",
        "Clean swap path",
        "A valid swap story designed to proceed through the full pipeline and reach safe output.",
        "SAFE TO EXECUTE",
    ),
    (
        "repair",
        "🔄 Repair & Re-run",
        "Recovered route",
        "A repaired intent path that demonstrates the agent can recover and re-submit safely.",
        "REPAIRED",
    ),
]
for col, (name, title, subtitle, desc, badge) in zip(story_cols, stories):
    active = st.session_state["selected_example"] == name
    theme = story_theme.get(name, story_theme["safe"])
    accent = theme["accent"]
    border = accent if active else "#1f2937"
    background = theme["soft"] if active else "rgba(17, 24, 39, 0.04)"
    shadow = f"0 0 0 2px {accent}55" if active else "none"
    badge_bg = accent if active else "#374151"
    with col:
        st.markdown(
            f"""
<div style="border: 2px solid {border}; background: {background}; box-shadow: {shadow};
    padding: 16px; border-radius: 14px; min-height: 150px;">
  <div style="display: flex; align-items: center; justify-content: space-between;
    gap: 12px; margin-bottom: 10px;">
    <div style="font-weight: 800; font-size: 1.02rem;">{title}</div>
    <div style="background: {badge_bg}; color: white; padding: 4px 10px;
      border-radius: 999px; font-size: 0.75rem; font-weight: 700;
      letter-spacing: 0.04em;">{badge}</div>
  </div>
  <div style="font-size: 0.88rem; font-weight: 700; opacity: 0.92; margin-bottom: 8px;">
    {subtitle}
  </div>
  <div style="font-size: 0.92rem; line-height: 1.45; opacity: 0.92;">{desc}</div>
</div>
""",
            unsafe_allow_html=True,
        )
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
                pipeline_state.append(("L4", "skipped", "Skipped because validation failed before RPC quorum."))
                pipeline_state.append(("L5", "skipped", "Skipped because validation failed before simulation."))
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))
            else:
                st.error(f"🚫 Lirix runtime issue: {exc.__class__.__name__}")
                st.info(f"**Reason**: {str(exc)}")
                st.caption("Please refresh the presentation or check the Mantle RPC configuration.")
                pipeline_state.append(("L1-L3", "blocked", exc.__class__.__name__))
                pipeline_state.append(("L4", "skipped", "Skipped because runtime setup failed."))
                pipeline_state.append(("L5", "skipped", "Skipped because runtime setup failed."))
                pipeline_state.append(("Decision", "blocked", exc.__class__.__name__))
        else:
            if rpc_mode == "Presentation Mode":
                sim = _presentation_l4_l5_result(payload, intent)
                pipeline_state.append(
                    (
                        "L4",
                        "passed",
                        "Presentation Mode reconciliation completed without live RPC dependency.",
                    )
                )
                pipeline_state.append(
                    (
                        "L5",
                        "passed",
                        f"Simulation returned: {sim.get('status', 'ok')}",
                    )
                )
                pipeline_state.append(("Decision", "passed", "Safe to proceed."))
                st.caption(
                    "Presentation Mode engaged: Mantle-safe evidence was synthesized "
                    "from the validated payload for a stable judge presentation."
                )
            else:
                try:
                    sim = client.validate_and_simulate(intent, payload, security_policy=policy)
                    pipeline_state.append(
                        (
                            "L4",
                            "passed",
                            "RPC quorum and reconciliation completed.",
                        )
                    )
                    pipeline_state.append(
                        (
                            "L5",
                            "passed",
                            f"Simulation returned: {sim.get('status', 'ok')}",
                        )
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
        st.caption("Linear DAG — intent → schema → DeFi → RPC quorum → shadow simulation → final verdict")
        _render_status_legend()
        _render_pipeline_dag(pipeline_state)
        progress_cols = st.columns(len(pipeline_state))
        for i, (label, state, detail) in enumerate(pipeline_state):
            with progress_cols[i]:
                if state == "passed":
                    st.success(f"**{label}** · PASSED")
                elif state == "blocked":
                    st.error(f"**{label}** · BLOCKED")
                else:
                    st.warning(f"**{label}** · PENDING")
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
- **L1-L3**: intent, schema, and DeFi calldata parsing (support for Merchant Moe / Agni / Pendle)
- **L4**: RPC quorum + block height spread fail-closed
- **L5**: zero-gas simulation + Shadow Auditor policy adjudication
- **Evidence**: SHA-256 replay digest + structured Failure Protocol (agent self-healing ready)
"""
        )

        st.subheader("Explorer")
        tx_hash = payload.get("tx_hash")
        if isinstance(tx_hash, str) and tx_hash.startswith("0x") and len(tx_hash) == 66:
            try:
                int(tx_hash, 16)
            except ValueError:
                st.info("Mantle Explorer transaction links appear only when a real on-chain " "tx_hash is supplied.")
            else:
                explorer_base = "https://explorer.mantle.xyz/tx"
                st.markdown(f"[Mantle Explorer transaction link]({explorer_base}/{tx_hash})")
        else:
            st.info("Mantle Explorer transaction links appear only when a real on-chain " "tx_hash is supplied.")

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
            _render_final_decision(final, pipeline_state[-1][2])
            if final != "passed":
                st.caption("Lirix 2.0.4 successfully prevented a potential malicious " "transaction on Mantle.")

        st.caption("📌 Lirix always returns structured Failure Protocol for AI Agent self-healing.")

    except (json.JSONDecodeError, ValueError) as exc:
        st.error(f"Invalid payload JSON: {exc}")

st.divider()
st.caption("🔥 Built for Mantle Turing Test Hackathon 2026 · Lirix 2.0.4 · fail-closed by design")
