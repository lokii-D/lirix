# API Reference / API 参考

**EN:** Public API surface, envelopes, migration flags, and broadcast-field extraction; several substrings are **`contract_manifest_gate`** anchors — preserve them verbatim when editing.

Single audit entrypoint (assertions → code → tests → evidence keys → CI gates): **[`docs/audit_path_map.md`](audit_path_map.md)**. Repo-wide Markdown conventions: [`documentation_styleguide.md`](documentation_styleguide.md).

## ⚡ Operator snapshot

This page is the **contract surface** for public symbols, return envelopes, and migration flags. The root package stays deliberately narrow—**`Lirix`**, **`LirixConfig`**, **`LirixSecurityException`**, and the frozen helpers listed below—while **`security_trace`**, **`validation_session`**, **`agent_feedback`**, and **`Lirix.extract_broadcast_fields`** carry the evidence story integrators automate against.

---

## English

### Recommended imports

- The authoritative frozen name set for the root package is **`_EXPECTED_ROOT_EXPORTS`** in **`tests/test_core/test_public_exports_contract.py`** (validated by **`test_root_package_exports_contract`**): membership is frozen, duplicates are disallowed, and ordering is non-semantic; the root package **`lirix`** exports **only** these names — currently **`Lirix`**, **`LirixConfig`**, **`LirixSecurityException`**, **`atomic_multicall`**, **`build_for_chain_profile`**, **`register_hook`**, **`replay_session`**, **`resolve_failure_protocol`**, **`verify_replay_bundle`**. Anything else — including **`HookManager`**, **`RPCManager`**, **`SandboxSimulator`**, **`ProxyPiercer`**, **`MulticallEncoder`**, other exceptions — must use **`from lirix.core import …`**, **`from lirix.core.exceptions import …`**, or **`from lirix.layers import …`** (and **`from lirix.audit.logger import AuditLogger`**). **`docs/migration_legacy_to_v2.md`** (**Root export policy**).
- **Monkeypatch rules (tests / integrations)** — pick exactly one binding per category:
  1. **Pipeline classes** (`IntentValidator`, `SchemaValidator`, `DeFiPayloadParser`, `RPCManager`, `SandboxSimulator`, …): patch **`lirix._client_core.<Symbol>`** (compat re-exports) **or** the concrete leaf module (**`lirix.layers.*`**), matching where `Lirix.chain_validate` binds validators today.
  2. **`Lirix` instance behavior only**: patch **`lirix.Lirix.<method>`** (implementation class: **`lirix._facade.Lirix`**) or `monkeypatch.setattr(lirix.Lirix, "validate_only", …)`; do **not** patch the bare **`lirix`** package module.
  3. **`verify_replay_bundle` when patching** (not when calling it directly): patch **`lirix._client_core.verify_replay_bundle`** — same object re-exported for `replay_session` / `Lirix.replay_from_bundle`; do not alias-swap multiple import paths for one bypass.

High-level entry points (see source for full signatures):

| Symbol | Role |
| ------ | ---- |
| `Lirix` | Main facade: hooks, audit, `chain_validate`, simulation helpers. |
| `LirixConfig` | Frozen Pydantic configuration with address normalization. |
| `atomic_multicall` | Encode Multicall3 calldata and run L1–L3 checks; **does not sign or broadcast**. |
| `register_hook` | Register hooks on `HookManager`. |
| `HookManager` | Sync/async hook dispatch with timeouts and audit integration. |
| Layer validators / `RPCManager` / `SandboxSimulator` | L1–L5 pipeline as implemented under `lirix.layers`; L4 primary runtime path is `RPCManager`. |

The exception lattice roots at `LirixBaseException`; only the security-oriented subset uses
subclasses of `LirixSecurityException`.

### `security_trace` Stable Contract (v1.0)

`validate_and_simulate` / `async_validate_and_simulate` return a `security_trace` with stable keys:

- `trace_version`
- `correlation_id`
- `intent`
- `input_summary`
- `payload_summary`
- `started_at`
- `steps[]`

Standardized evidence payloads in `steps[]` include:

- `QuorumVerdict` (L4 consensus result)
- `RPCDisagreementReport` (L4 disagreement evidence; `taxonomy` includes `reason_code` / `raw_reason_code` / `canonical_reason_code` / `severity` / `remediation`)
- `SimulationOutcome` (L5 factual output with replay fields: `assumptions` / `state_delta_digest` / `policy_match_ids`)
- `PolicyDecision` (policy-layer verdict)

Compatibility policy:

- additive changes only for existing payloads;
- existing `validated`, `simulation_ok`, and `return_data` semantics stay unchanged;
- any `trace_version` bump will be documented with migration notes in release notes.

### `validation_session` (Session-level Security Context)

Evidence-emitting entry points (`validate_only`, `async_validate_only`, `simulate_only`, `async_simulate_only`, `validate_and_simulate`, `async_validate_and_simulate`) return an additional `validation_session` payload (additive-only for compatibility). It supports multi-turn agent workflows and includes:

- `session_id`
- `created_at`
- `correlation_ids` produced inside the session
- `timeline[]` (both `record_trace` and `session_event` entries)
- `state` for orchestrators to persist intermediate state
- `decision_log` structured decision events
- `lifecycle` current session lifecycle state

Timeline compatibility: additive changes only; existing entry kinds are not removed.

Additional local replay/forensic outputs:

- `replay_bundle`: session-level replay package (with `bundle_digest`).
- `forensic_bundle`: failure-focused bundle (with `error_codes` and `canonical_error_codes`).
- `forensic_bundle.raw_error_codes`: explicit raw-code set aligned with `error_codes`.
- `forensic_bundle.reason_codes` / `forensic_bundle.canonical_reason_codes`: deprecated compatibility aliases.
- `forensic_bundle.agent_reason_codes`: forensic-level reason codes aligned with `agent_feedback.reason_code`.

### `agent_feedback` (Fail-Closed Correction Envelope)

Evidence-emitting entry points include `agent_feedback`. On failure, the same object is also attached to exception `context` for deterministic agent remediation.

Stable fields:

- `schema_version`
- `failure_type`
- `layer`
- `reason_code` (fixed enum, e.g. `LIRIX_REASON_OK`, `LIRIX_REASON_TIMEOUT`)
- `retry_allowed`
- `remediation`
- `details`

Compatibility policy:

- `reason_code` follows a fixed additive taxonomy;
- `canonicalize_reason_code(raw, strict=True)` rejects unknown prefixed reason codes and falls back to `LIRIX_REASON_UNKNOWN`;
- debug fields may be appended under `details` (for example `raw_reason`).

### Migration Modes

`LirixConfig` now includes additive migration flags:

- `hook_contract_mode`: `legacy | warn | shadow | enforce`
- `policy_lifecycle_mode`: runtime target is `digest_verified` (`legacy` / `signed_only` are migration-only aliases and are coerced)
- `rpc_evidence_mode`: runtime target is `v2_only` (`legacy` / `v2_dual` are migration-only aliases and are coerced)

Policy lifecycle and rollback semantics are specified in:

- `docs/policy_lifecycle_and_rollback.md`

All high-level returns now include additive metadata:

- `evidence_schema_version`
- `migration_modes`

### Developer Paths

- `validate_only(intent, payload)` for L1-L3-only validation.
- `simulate_only(payload)` for L4-L5 factual simulation only.
- `validate_and_simulate(intent, payload)` for full pipeline.
- `atomic_multicall(...)` for batch-safe transaction packing.
- `replay_session(bundle)` for local replay bundle verification/extraction.
- `Lirix.resolve_failure_protocol(context)` to project `failure_protocol` back to agent feedback shape.
- `lirix.integrations.langchain` and `lirix.integrations.autogen` for framework entrypoints.

### Broadcast fields from the result envelope (`validate_and_simulate` / `async_validate_and_simulate`)

- **Recommended**: `Lirix.extract_broadcast_fields(result)` reads only `result["payload"]` and returns `{"to", "data", "value"}` (same subtree as `simulation_outcome` / `simulation_ok` mirrored by `ResultBuilder.build_base_result`).
- **Equivalent manual path**: `p = result["payload"]`, then `p["to"]` / `p["data"]` / `p.get("value", 0)`; do not assume `to`/`data` exist at the top level of the envelope.
- **Strict (fail-closed) mode**: iff `result["decision"] == "approved"` and `result["status"] == "approved"`, missing **non-empty string** `to` / `data` under `payload` (`None`, empty string, or non-`str`) causes `LirixSecurityException` with `context["reason"] == "approved_broadcast_fields_invariant"` and `canonical_error_code` / `context["canonical_error_code"]` set to `LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT`. Non-approved envelopes keep the permissive `None` placeholders.
- **Mainline assertion aligned with integration tests**: `result["decision"] == "approved"` and `result["payload"]["simulation_ok"] is True` (see `tests/test_integration/test_real_e2e_paths.py`).

### Multi-chain Adaptation (`chain_profile`)

`LirixConfig.chain_profile` supports optional registry domains:

- `protocol_registry`: protocol name -> address
- `address_registry`: token/alias -> address
- `simulation_backend_profile`: simulation backend preferences (provider/mode/fork metadata)

---

## 中文

**中文：** 对外 API、返回信封、迁移开关与广播字段提取说明；文中多处子串为 **`contract_manifest_gate`** 锚点，改写时须原样保留。

审计单一入口（断言→代码→测试→证据键→CI 门禁）见：**[`docs/audit_path_map.md`](audit_path_map.md)**。全仓文档体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

以下为高层入口，完整签名以源码与类型标注为准。

| 符号 | 说明 |
| ---- | ---- |
| `Lirix` | 主入口：挂载 `HookManager`、`AuditLogger`。取证与回放优先使用 **`validate_only` / `simulate_only` / `validate_and_simulate`**；`chain_validate` 仅为 `validate_only` 同路径上的 **`bool` 糖衣**（成功返回 `True`）。 |
| `LirixConfig` | Pydantic 冻结配置；初始化时完成地址规范化与约束检查。 |
| `atomic_multicall` | 将多笔子调用编码为 Multicall3 单笔 calldata，并走 L1–L3 校验；**不签名、不广播**。 |
| `register_hook` | 在 `HookManager` 上注册钩子（与 `HookManager.register_hook` 等价）。 |
| `HookManager` | 同步/异步钩子调度、隔离超时、审计绑定；**`from lirix.core import HookManager`**。 |
| `IntentValidator` / `SchemaValidator` / `DeFiPayloadParser` | L1 / L2 / L3 分层校验（与 **`Lirix.validate_only`** 同源；`chain_validate` 可选用于仅需布尔结果的调用方）。 |
| `RPCManager` / `SandboxSimulator` | L4 / L5：RPC 协调与 `eth_call` 沙盒模拟（需有效 RPC 配置）；**`from lirix.layers import …`**。L4 的标准主路径是 `RPCManager`。`AsyncQuorumProvider` 仅为非主路径兼容组件，快照会标注 `path_role=secondary_non_primary` 与 `usage_warning`，不应作为新生产流入口。 |

异常体系以 `LirixBaseException` 为根；仅安全相关子集继承自 `LirixSecurityException`（见 `lirix.core.exceptions`）。

### `security_trace` 稳定契约（v1.0）

`validate_and_simulate` / `async_validate_and_simulate` 返回的 `security_trace` 包含以下稳定字段：

- `trace_version`
- `correlation_id`
- `intent`
- `input_summary`
- `payload_summary`
- `started_at`
- `steps[]`

`steps[]` 中的标准化证据对象包含：

- `QuorumVerdict`（L4 共识结论）
- `RPCDisagreementReport`（L4 分歧证据，`taxonomy` 含 `reason_code` / `raw_reason_code` / `canonical_reason_code` / `severity` / `remediation`）
- `SimulationOutcome`（L5 事实输出，含可回放字段：`assumptions` / `state_delta_digest` / `policy_match_ids`）
- `PolicyDecision`（策略层裁决）

兼容策略：

- 仅新增字段，不删除既有字段；
- 既有 `validated`、`simulation_ok`、`return_data` 语义保持不变；
- `trace_version` 变更时会在发布说明中注明迁移信息。

### `validation_session`（会话级安全上下文）

证据型高层入口（`validate_only` / `simulate_only` / `validate_and_simulate` / `async_validate_and_simulate`）在返回中附带 `validation_session`（新增字段，兼容旧调用方）。它用于多轮 Agent 工作流的可追踪生命周期，包含：

- `session_id`：会话 ID
- `created_at`：创建时间
- `correlation_ids`：本会话内产生的 `security_trace.correlation_id` 列表
- `timeline[]`：会话时间线（`record_trace` 与 `session_event` 两类条目）
- `state`：会话级可变状态（供上层编排器写入）。若启用 `LirixConfig.simulate_only_requires_prior_validate`，集成方应在日志/告警中关注 **`state["l1_l3_ok"]`**（亦见于 `validation_session` 快照）；语义与钩子顺序见 **[Session gate semantics (l1_l3_ok)](audit_path_map.md#session-gate-semantics-l1_l3_ok)**。
- `decision_log`：结构化决策事件日志
- `lifecycle`：会话生命周期状态

`timeline[]` 兼容策略：只追加字段，不删除既有条目类型。

新增本地取证与回放输出：

- `replay_bundle`：会话级可重放包（含 `bundle_digest`）。
- `forensic_bundle`：失败事件归档（含 `error_codes` 与 `canonical_error_codes`）。
- `forensic_bundle.raw_error_codes`：与 `error_codes` 同步的显式原始错误码集合（新增明确语义字段）。
- `forensic_bundle.reason_codes` / `forensic_bundle.canonical_reason_codes`：兼容别名（deprecated）。
- `forensic_bundle.agent_reason_codes`：与 `agent_feedback.reason_code` 同步的取证级原因码。

### `agent_feedback`（Fail-Closed 纠正反馈）

证据型高层入口会返回 `agent_feedback`。失败时，该对象也会被写入异常 `context`，用于上层 Agent 自动修正。

稳定字段：

- `schema_version`
- `failure_type`
- `layer`
- `reason_code`（固定枚举，例如 `LIRIX_REASON_OK`、`LIRIX_REASON_TIMEOUT`）
- `retry_allowed`
- `remediation`
- `details`

失败路径附带的 `failure_protocol` 稳定字段：

- `schema_version`
- `failure_layer`
- `failure_type`
- `failure_type_canonical`
- `retryable`
- `repair_hint`
- `human_action_required`
- `details`

兼容策略：

- `reason_code` 采用固定 taxonomy（向后只增不改）；
- `canonicalize_reason_code(raw, strict=True)` 在严格模式下会拒绝未知 `LIRIX_REASON_*` 并回落到 `LIRIX_REASON_UNKNOWN`；
- 允许在 `details` 中追加调试字段（如 `raw_reason`）。

### 迁移开关（兼容优先）

`LirixConfig` 新增分域迁移开关（默认均为兼容模式）：

- `hook_contract_mode`: `legacy | warn | shadow | enforce`
- `policy_lifecycle_mode`: runtime fixed to `digest_verified`; `legacy` / `signed_only` are input aliases that normalize to this mode
- `rpc_evidence_mode`: runtime fixed to `v2_only`; `legacy` / `v2_dual` are input aliases that normalize to this mode

高层返回中新增：

- `evidence_schema_version`
- `migration_modes`

以上字段均为新增字段，不影响旧调用方。

### 开发者入口路径

- `validate_only(intent, payload)`：仅执行 L1-L3 校验。
- `async_validate_only(intent, payload)`：异步 L1-L3（与 `validate_only` 同构）。
- `simulate_only(payload)`：仅执行 L4-L5 事实模拟。
- `async_simulate_only(payload)`：异步 L4-L5（与 `simulate_only` 同构）。
- `validate_and_simulate(intent, payload)`：标准全链路（L1-L5 + policy）。
- `atomic_multicall(client, intent, transactions)`：批量子调用打包；校验路径与 `validate_only` 一致，并可附加 `replay_bundle` 等取证字段。
- `chain_validate(intent, payload)`：布尔返回值；内部委托 `validate_only`（取证一致）。
- `replay_session(bundle)`：本地验证并提取会话快照（零遥测）。
- `Lirix.resolve_failure_protocol(context)`：将 `failure_protocol` 还原为 `agent_feedback` 形态。
- `lirix.integrations.langchain`：LangChain 工具入口。
- `lirix.integrations.autogen`：AutoGen 工具入口。

### 从返回信封提取广播字段（`validate_and_simulate` / `async_validate_and_simulate`）

- **推荐**：`Lirix.extract_broadcast_fields(result)`，内部只读 `result["payload"]`，返回 `{"to", "data", "value"}`（与 `ResultBuilder.build_base_result` 提升的 `simulation_ok` / `simulation_outcome` 同源子树）。
- **等价手写**：`p = result["payload"]`，再读 `p["to"]` / `p["data"]` / `p.get("value", 0)`；不要假设 `to`/`data` 在返回字典顶层。
- **严格模式（fail-closed）**：当且仅当 `result["decision"] == "approved"` 且 `result["status"] == "approved"` 时，若 `payload` 缺少**非空字符串**的 `to` / `data`（含 `None`、空串、非 `str`），`extract_broadcast_fields` 抛出 `LirixSecurityException`，`context["reason"] == "approved_broadcast_fields_invariant"`，`canonical_error_code` / `context["canonical_error_code"]` 为 `LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT`。其他决策路径仍返回宽松占位（`to`/`data` 可为 `None`）。
- **与集成测试对齐的主线断言**：`result["decision"] == "approved"` 且 `result["payload"]["simulation_ok"] is True`（见 `tests/test_integration/test_real_e2e_paths.py`）。

### 多链适配配置（`chain_profile`）

`LirixConfig.chain_profile` 支持以下注册域（均为可选）：

- `protocol_registry`：协议名 -> 地址
- `address_registry`：资产/别名 -> 地址
- `simulation_backend_profile`：模拟后端配置（如 provider/mode/fork 参数）
- `registry_version` / `registry_source`：注册表治理元信息（可用于回放闭包与审计标注）。
