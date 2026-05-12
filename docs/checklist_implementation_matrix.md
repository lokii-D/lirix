# Checklist Implementation Matrix / 清单实现矩阵


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

### English

Maps checklist items to code locations, acceptance assertions, gates, and evidence keys for release sign-off and regression audits.

### 中文

本文件将架构清单逐条映射到当前代码与可执行验收点，用于发布前签署与回归审计。

审计单一入口（断言→代码→测试→证据键→CI 门禁）见：**[`docs/audit_path_map.md`](audit_path_map.md)**。

## P0 必做项

| 清单项 | 代码落点 | 验收断言 |
| ---- | ---- | ---- |
| 统一支持矩阵与运行边界 | `pyproject.toml` / `lirix/__init__.py` / `.github/workflows/ci.yml` / `README.md` | Python 边界统一为 `3.9 <= version < 3.15`，文档与运行时错误信息一致。 |
| 统一 evidence 对象 | `lirix/core/evidence.py` / `lirix/__init__.py` | `SecurityTrace.steps[]` 使用标准对象：`ExecutionEvidence` / `QuorumVerdict` / `RPCDisagreementReport` / `SimulationOutcome` / `PolicyDecision`。 |
| 会话级上下文抽象 | `lirix/core/session.py` / `lirix/__init__.py` | 证据型高层入口（`validate_only`/`simulate_only`/`validate_and_simulate`/`async_validate_and_simulate`）返回 `validation_session`，包含 `timeline`、`decision_log`、`correlation_ids`。 |
| 收紧 hook contract | `lirix/core/hook_manager.py` / `lirix/core/constants.py` | `HookPatch` 仅允许 `pre_validate`/`pre_simulation`，其他点位在 `enforce` 下返回 `LIRIX_HOOK_PATCH_FORBIDDEN`。 |
| Hook patch target 边界 | `lirix/core/hook_manager.py` / `lirix/core/hook_contract.py` | `HookPatch.target != payload` 在 `enforce` 下返回 `LIRIX_HOOK_PATCH_TARGET_FORBIDDEN`，在 `warn/shadow` 产生显式 warning。 |
| L4 可解释共识系统 | `lirix/layers/l4_rpc_manager.py` / `lirix/core/evidence.py` | `rpc_disagreement_report.taxonomy.*` 必含 `reason_code`、`severity`、`remediation`。 |

## P1 增强项

| 清单项 | 代码落点 | 验收断言 |
| ---- | ---- | ---- |
| policy bundle + versioning | `lirix/layers/l5_shadow_auditor.py` | 支持 `PolicyBundle`、`PolicyVersion`、`PolicyConflict`，可输出冲突解释。 |
| policy rollback | `lirix/layers/l5_shadow_auditor.py` | 选中版本非 `active` 且配置 `rollback_to` 时，报告 `rollback_applied=true` 并切回目标版本。 |
| 模拟结果标准化 | `lirix/core/evidence.py` / `lirix/__init__.py` | `SimulationOutcome` 输出 `assumptions`、`state_delta_digest`、`policy_match_ids`。 |
| 多链适配可插拔 | `lirix/core/chain_adapter.py` | `chain_profile` 支持 `protocol_registry`、`address_registry`、`simulation_backend_profile` 并可解析。 |
| fail-closed 反馈协议 | `lirix/core/constants.py` / `lirix/core/evidence.py` / `lirix/core/failure_protocol.py` / `lirix/__init__.py` | 固定 `agent_feedback.reason_code` taxonomy；`failure_protocol.failure_type_canonical` 与 `forensic_bundle.canonical_error_codes` 保持一致；失败路径给出 `retry_allowed` 与 `remediation`。 |
| 顶层导向式 API | `lirix/__init__.py` / `README.md` / `docs/quickstart.md` | 明确四条入口：`validate_only`、`simulate_only`、`validate_and_simulate`、`atomic_multicall`。 |

## P2 收束项

| 清单项 | 代码落点 | 测试路径 | 证据键 | CI 门禁 |
| ---- | ---- | ---- | ---- | ---- |
| replay / forensic | `lirix/core/session.py` / `lirix/__init__.py` | `tests/test_core/test_session.py`, `tests/test_core/test_session_replay_verifier_malformed_shapes.py` | `replay_bundle.*`, `forensic_bundle.*` | Governance gate |
| replay closure 重算一致性 | `lirix/core/config_fingerprint.py` / `lirix/__init__.py` / `lirix/core/session.py` | `tests/test_core/test_replay_registry_closure_binding.py`, `tests/test_core/test_replay_registry_closure_parity_all_entrypoints.py` | `replay_bundle.registry_closure_digest` | Governance gate |
| 本地结构化可观测（零遥测） | `lirix/core/session.py` / `lirix/core/evidence.py` | `tests/test_core/test_session.py` | `security_trace.*`, `validation_session.*` | Governance gate |
| 接入路径文档地图 | `README.md`, `docs/api_reference.md`, `docs/quickstart.md` | `tests/test_core/test_readme_envelope_contract.py` | 文档锚点（入口/返回键/兼容策略） | Docs contract gate（`python tools/harness.py contract-manifest`） |
| 根 import 表面 + Monkeypatch 规范 | `python tools/harness.py root-import-surface` / `python tools/harness.py test-monkeypatch-convention --strict` / `.github/workflows/ci.yml` | `tests/test_core/test_public_exports_contract.py` | `lirix.__all__` | `harness.py root-import-surface` + `harness.py test-monkeypatch-convention --strict` |
| 广播不变量 / `extract_broadcast_fields` / 集成 `tx_payload` 闭环 | `lirix/_facade.py`（双 `approved` 严格路径 + `Lirix.extract_broadcast_fields`）、`lirix/integrations/langchain/tool.py::_serialize_guardian_success`、`lirix/integrations/autogen/tool.py` | `tests/test_core/test_readme_envelope_contract.py`, `tests/test_integrations/test_langchain_tool_run_arun_delegate_to_guardian_paths.py` | 阻断：`context["reason"] == "approved_broadcast_fields_invariant"`, `canonical_error_code == "LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT"`；成功：JSON 中 additive `tx_payload`（镜像 `extract_broadcast_fields` 视图；非 JSON fallback 不注入） | Governance gate + Docs contract gate（`python tools/harness.py contract-manifest`） |

## 发布前 Gate（必须全部通过）

- `pytest` 通过新增与关键回归测试（hook/session/policy/rpc evidence/chain profile）。
- `ReadLints` 对改动文件返回 0 错误。
- `docs/release_notes.md` 记录 `API Contract Delta` 且声明 additive compatibility。
- 文档中所有新增字段与真实返回键名完全一致（逐字段比对）。
- CI 显式 governance gate 覆盖 canonical/session/entrypoints/hook/langchain 及关键 L4/L5 治理回归集。
- 文档与契约门禁（与 **`docs/audit_path_map.md`** § CI 对齐）：`python tools/harness.py contract-manifest`、`python tools/harness.py audit-internal-link`、`python tools/harness.py root-import-surface`、`python tools/harness.py test-monkeypatch-convention --strict`。

## 重点回归用例（建议最小集）

- `tests/test_core/test_hook_manager.py`
- `tests/test_core/test_canonical_semantics.py`
- `tests/test_core/test_session.py`
- `tests/test_core/test_session_workflow_strict_happy_path.py`
- `tests/test_core/test_evidence_models.py`
- `tests/test_core/test_chain_adapter_profiles.py`
- `tests/test_core/test_replay_registry_closure_binding.py`
- `tests/test_layers/test_l4_rpc_manager_disagreement_report.py`
- `tests/test_layers/test_shadow_auditor_policy_bundle.py`
