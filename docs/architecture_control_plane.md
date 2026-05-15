# Lirix Control Plane Architecture

**EN:** Control-plane assertion table only (config, session, replay, hooks, chain profiles → code → tests → evidence keys). Not the audit index; not API contract prose.<br>
**中文：** 仅承载控制面断言表（配置、会话、回放、钩子、链配置 → 代码 → 测试 → 证据键）。非审计总入口，非 API 契约正文。

The control plane is the **auditable join** between configuration authority, layered validators, and typed evidence keys—nothing here is decorative prose.

> **Audit index (navigation):** [`docs/audit_path_map.md`](audit_path_map.md) — sole entry for architecture → code → tests → evidence → CI.<br>
> **Gate semantics (`l1_l3_ok`, full-pipeline revalidation):** defined only in [`audit_path_map.md` § Session gate semantics](audit_path_map.md#session-gate-semantics-l1_l3_ok); this file links, does not restate.

**Core vs layers (dependency inversion):** `lirix/core/layer_ports.py` defines the `Protocol` contracts (`RpcEvidenceSource`, `PipelineLayerExecutor`) so `lirix.core` orchestration stays free of `lirix.layers` imports; `lirix/_layer_factories.py` holds the concrete L4/L5 factory wiring consumed from `lirix/_facade.py`.

---

## 🏛️ Control Plane Assertions

| Assertion | Code Path | Test Path | **Evidence Key** |
| --- | --- | --- | --- |
| Config precedence is deterministic and authority-driven | `lirix/core/config_authority.py`, `lirix/__init__.py` | `tests/test_core/test_config_authority_precedence.py` | `config_source_tags` |
| Session lifecycle is replay-safe; `workflow_mode` selects agent vs direct; replay verifier exposes `enforce_agent_timeline_order` | `lirix/core/session.py`, `lirix/core/session_fsm.py` | `tests/test_core/test_session.py`, `tests/test_core/test_session_agent_timeline_order_happy_path.py` | `validation_session.lifecycle`, `timeline`, `decision_log`, `replay_bundle.payload.workflow_mode` |
| Replay closure binds config + registry snapshots | `lirix/core/config_fingerprint.py`, `lirix/core/session.py`, `lirix/__init__.py` | `tests/test_core/test_replay_registry_closure_binding.py` | `replay_bundle.config_fingerprint`, `replay_bundle.registry_closure_digest` |
| Replay verifier strict path is available at top-level API boundary | `lirix/_client_facade.py::replay_session`, `lirix/core/session.py::verify_replay_bundle` | `tests/test_core/test_replay_registry_closure_parity_all_entrypoints.py`, `tests/test_core/test_session_replay_verifier_malformed_shapes.py` | `replay_bundle.replay_proof.*` |
| Failure protocol and agent feedback are structurally bridged with canonical semantics | `lirix/core/constants.py`, `lirix/core/failure_protocol.py`, `lirix/core/evidence.py`, `lirix/__init__.py` | `tests/test_core/test_session.py`, `tests/test_core/test_canonical_semantics.py` | `failure_protocol.failure_type_canonical`, `agent_feedback.reason_code`, `forensic_bundle.canonical_error_codes` |
| Hook patch boundary is governed by contract mode | `lirix/core/hook_manager.py`, `lirix/core/hook_contract.py` | `tests/test_core/test_hook_manager.py` | `hook_result.error_code`, `failure_level`, `patch_allowed` |
| Hook trace status reflects isolated execution aggregate state | `lirix/core/hook_manager.py::_maybe_record_hook_trace` | `tests/test_core/test_hook_governance_async_contract_mode_parity.py` | `security_trace.steps[].status=ok|degraded` |
| Chain profile registry is strict-mode gated by allowlist | `lirix/__init__.py`, `lirix/core/chain_adapter.py` | `tests/test_core/test_plan_alignment_hardening_coverage.py` | `ConfigurationGuardException.context.reason=registry_allowlist_required` |
| Chain profile runtime policy is actually consumed by L4/L5 builders | `lirix/_facade.py::_build_rpc_manager`, `lirix/_facade.py::_build_sandbox_simulator`, `lirix/layers/l5_sandbox_simulator.py` | `tests/test_core/test_chain_adapter_profiles.py` | `security_trace.steps[].details.simulation.backend_profile` |
| L4 evidence carries chain context for cross-layer explainability | `lirix/_facade.py`, `lirix/core/orchestrator.py` | `tests/test_core/test_coverage_closure_v16.py` | `security_trace.steps[].details.chain_context` |
| Session `l1_l3_ok` | `lirix/_facade.py::_mark_session_l1_l3_ok`, `lirix/core/orchestrator.py` (`run_validate`, `run_full`) | `tests/test_core/test_simulate_only_prior_validate_config.py`, `tests/test_core/test_simulate_only_gate_semantics.py`, `tests/test_core/test_simulate_only_gate_matrix.py`, `tests/test_core/test_run_full_l1_l3_revalidation.py` | **`validation_session.state.l1_l3_ok`** → [`§ Session gate semantics`](audit_path_map.md#session-gate-semantics-l1_l3_ok) |
| `run_full` post–`HOOK_PRE_SIMULATION` L1–L3 revalidation (fail-closed; same draft) | `lirix/core/orchestrator.py::LirixPipelineOrchestrator.run_full` → `_run_l1_l3_validation`, `_record_failure` | `tests/test_core/test_run_full_l1_l3_revalidation.py` | `validation_session.timeline`, `exception.context.agent_feedback`, `exception.context.failure_protocol` → [`§ Session gate semantics`](audit_path_map.md#session-gate-semantics-l1_l3_ok) |

---

## ⚡ Execution Pipeline

1. `resolve_config()` composes runtime config and governance modes.
2. `ChainAdapter` materializes profile, registry snapshots, decoder resolution.
3. L1-L5 pipeline emits `SecurityTrace` + v2 evidence.
4. `ValidationSession` writes replay/forensic artifacts with closure digests.
5. Failure paths emit `agent_feedback` and `failure_protocol` for repair orchestration.

---

## 🛡️ Compatibility Contract

- Default behavior remains backward-compatible.
- Strict governance hardening is opt-in via explicit modes.
- All closure enhancements are additive fields (no existing keys removed).

### 中文（对照）

上文 **Control Plane Assertions** 表给出「断言 → 实现路径 → 测试 → 证据键」的闭包；其中 **`failure_protocol.failure_type_canonical`**、**`forensic_bundle.canonical_error_codes`** 与 **`tests/test_core/test_canonical_semantics.py`** 等子串为契约门禁所依赖，改写时须保留。执行管线五步（配置解析 → 链适配 → L1–L5 → 会话取证 → 失败协议）与英文 **Execution Pipeline** 一节一致。体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。
