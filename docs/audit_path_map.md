---
title: Audit Path Map
purpose: architecture -> code -> tests -> evidence -> CI gate
compatibility: additive-only; single-stack runtime with legacy aliases as input-only compatibility
---

**EN:** Single source of audit truth — each row links assertions to code, tests, evidence keys, and CI gates.<br>
**中文：** 审计单一事实来源：每行将断言映射到实现、测试、可观测证据键与 CI 门禁。双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

---

## 🔧 Harness alignment (terminology)

In this repository, **Harness** refers only to an **engineering methodology** aligned with GitHub Actions: **layered gates**, a **single source of truth** for audits and exclusions (`docs/audit_path_map.md`, `docs/repo_exclusions.md`, contract gates), **optional slow lanes** vs **mainline** responsibilities, and a **repeatable verification narrative** (see `docs/ci_gate_matrix.md`). We **do not** integrate Harness.io, Drone, or other external CD SaaS.

---

# Audit Path Map (Single Source of Audit Truth)

This document is the single audit entrypoint for Lirix. Each assertion maps to:

- code path (authoritative implementation)
- test path (executable proof)
- evidence keys (observable payload surface)
- CI gate (where it is enforced)

---

## 🗂️ Scope / Exclusions

- Authoritative four-way alignment: **`docs/repo_exclusions.md`** (`.gitignore`, `pyproject.toml` `norecursedirs`, this section, **`.harnessignore`**).
- Explicitly out of scope: `tdsc/`, `mantle_TT/`.
- **`lirix.shield`** is a legacy namespace (see **`docs/migration_legacy_to_v2.md`**); not treated as a stability-bound public surface alongside **`lirix.layers`**.

---

## 📐 ADR-lite: empty resolved decoder plugins (test alignment only)

`tests/test_core/test_chain_adapter_profiles.py::test_resolved_decoder_digest_matches_when_allowlist_equals_compat_resolution` may set `decoder_policy: "explicit_only"` on the **runtime_patch** `chain_profile` when `Lirix._resolved_decoder_plugins()` returns an **empty** list. That mirrors **`explicit_only`** semantics for digest construction so the test can compare baseline vs patched digests without tripping “empty allowlist” invalid combinations.

**Product / runtime default is unchanged:** `build_chain_profile` / `ChainAdapter` still **reject** `decoder_plugins: []` for non–`explicit_only` policies (see `tools/compat_switch_expiry.py`). No new production default forces `explicit_only` for empty plugin lists; the above is **test-only** alignment, not a silent behavior change.

---

## 🧾 Core Assertions Map

| Assertion | Code path | Test path | **Evidence keys** | CI gate |
| --- | --- | --- | --- | --- |
| Canonical semantics are stable and additive (single-stack runtime) | `lirix/core/constants.py`, `lirix/core/canonical_taxonomy.py`, `lirix/core/exceptions.py`, `lirix/core/evidence.py` | `tests/test_core/test_canonical_semantics.py`, `tests/test_core/test_agent_feedback_reason_taxonomy_closure.py` | **`exception.canonical_error_code`**, **`agent_feedback.reason_code`**, **`agent_feedback.retry_allowed`**, **`agent_feedback.remediation`** | Governance gate |
| Failure protocol -> agent feedback bridge is canonicalized | `lirix/core/failure_protocol.py` | `tests/test_core/test_canonical_semantics.py` | **`failure_protocol.failure_type_canonical`**, **`agent_feedback.failure_type`** | Governance gate |
| Session timeline producer and verifier stay closure-consistent | `lirix/core/session.py`, `lirix/core/session_fsm.py`, `lirix/core/forensic_verifier.py` | `tests/test_core/test_session.py`, `tests/test_core/test_session_replay_verifier_malformed_shapes.py`, `tests/test_core/test_session_agent_timeline_order_happy_path.py` | **`validation_session.timeline`**, **`validation_session.lifecycle`**, **`validation_session.state.session_outcome`**, **`replay_bundle.payload.timeline`**, **`forensic_bundle.replay_bundle_digest`** | Governance gate |
| Replay bundle integrity is fail-closed; optional `enforce_agent_timeline_order` enforces agent FSM order on replay | `lirix/core/session.py::verify_replay_bundle`, `lirix/_client_facade.py::replay_session` | `tests/test_core/test_session.py`, `tests/test_core/test_session_replay_verifier_malformed_shapes.py` | `replay_bundle.bundle_digest`, `replay_bundle.replay_proof.*`, `replay_bundle.artifact_digests`, `replay_bundle.payload.workflow_mode` | Governance gate |
| Replay closure binds config + registries + runtime semantics | `lirix/core/config_fingerprint.py`, `lirix/_facade.py` (`Lirix` pipeline surface) | `tests/test_core/test_replay_registry_closure_binding.py`, `tests/test_core/test_replay_registry_closure_parity_all_entrypoints.py` | `replay_bundle.config_fingerprint`, `registry_closure_digest`, `replay_proof.chain_registry_digest`, `replay_proof.decoder_registry_digest`, `artifact_digests.ext_resolved_decoder_plugins_digest` | Governance gate |
| Chain profile runtime policy is consumed by L4/L5 and frozen into evidence | `lirix/_facade.py::_build_rpc_manager`, `lirix/_facade.py::_build_sandbox_simulator`, `lirix/core/chain_adapter.py` | `tests/test_core/test_chain_adapter_profiles.py` | `security_trace.steps[].details.chain_context`, `security_trace.steps[].details.runtime_semantics`, `evidence_v2.l4.details.runtime_semantics` | Governance gate |
| Hook contract boundary is governed; hook trace status is aggregated deterministically | `lirix/core/hook_manager.py`, `lirix/core/hook_contract.py`, `lirix/core/status_aggregation.py` | `tests/test_core/test_hook_manager.py`, `tests/test_core/test_hook_governance_async_contract_mode_parity.py`, `tests/test_core/test_status_aggregation.py` | `hook_result.error_code`, `patch_allowed`, `failure_level`, `trace.steps[].status` | Governance gate |
| Governance mode overlap and dependency checks are closed-world | `lirix/core/config_governance.py` | `tests/test_core/test_config_governance_overlap_guards.py` | `ConfigurationGuardException.context.reason` | Governance gate |
| Public exports and entrypoint symbols do not drift | `lirix/__init__.py`, `lirix/core/__init__.py`, `lirix/layers/__init__.py` | `tests/test_core/test_public_exports_contract.py`, `tests/test_core/test_entrypoint_symbol_binding_contract.py` | `__all__` surfaces | Governance gate |
| Policy rollback behavior is evidence-visible | `lirix/layers/l5_shadow_auditor.py` | `tests/test_layers/test_shadow_auditor_policy_bundle.py` | `policy_decision.bundle.rollback_applied`, `policy_decision.lifecycle_mode` | Governance gate |
| `l1_l3_ok` matches every entry that completes L1-L3 on a session | `lirix/_facade.py::_mark_session_l1_l3_ok`, `lirix/core/orchestrator.py::LirixPipelineOrchestrator.run_validate`, `lirix/core/orchestrator.py::LirixPipelineOrchestrator.run_full` | `tests/test_core/test_simulate_only_prior_validate_config.py`, `tests/test_core/test_simulate_only_gate_semantics.py`, `tests/test_core/test_simulate_only_gate_matrix.py`, `tests/test_core/test_run_full_l1_l3_revalidation.py` | `validation_session.state.l1_l3_ok`, `ConfigurationGuardException.context.reason` when gate blocks | Governance gate |
| `run_full` L1–L3 re-check failure after `HOOK_PRE_SIMULATION` is fail-closed with full `_record_failure` audit (no L4/L5) | `lirix/core/orchestrator.py::LirixPipelineOrchestrator.run_full` → `_record_failure` | `tests/test_core/test_run_full_l1_l3_revalidation.py` | `validation_session.timeline` (`kind=validate_and_simulate`, `status=rejected`), `exception.context.agent_feedback`, `exception.context.failure_protocol` | Governance gate |
| Broadcast extract is strict (fail-closed) only on dual `approved`; integrations add `tx_payload` on JSON success | `lirix/_facade.py` (`Lirix.extract_broadcast_fields`, dual-`approved` strict `to`/`data`), `lirix/integrations/langchain/tool.py::_serialize_guardian_success`, `lirix/integrations/autogen/tool.py` | `tests/test_core/test_readme_envelope_contract.py`, `tests/test_integrations/test_langchain_tool_run_arun_delegate_to_guardian_paths.py` | `context["reason"] == "approved_broadcast_fields_invariant"`, `canonical_error_code == "LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT"`; success JSON additive `tx_payload` mirrors `extract_broadcast_fields` (non-JSON fallback `str(result)` does not inject) | Governance gate + Docs contract gate (`python tools/harness.py contract-manifest`) |
| Root `from lirix import` usage in ancillary trees stays within frozen `lirix.__all__` | `tools/validators.py::check_root_import_surface` | `tests/test_core/test_public_exports_contract.py` | `lirix.__all__` bounded surface (scanner-enforced) | Root import surface gate |
| CLI scaffold (`lirix init`) stays stable | `lirix/cli.py` | `tests/test_core/test_cli_public_contract.py`（parser / scaffold / `python -m lirix.cli`、README `lirix init`、冻结子命令集合） | generated scaffold files + exit code `0` | Governance gate |

---

## 📦 Supporting subtrees (registry / intents / audit)

Subtree directories **`lirix/registry/`**, **`lirix/intents/`**, **`lirix/audit/`** each contain only `__init__.py` plus one implementation module — the table below lists every file so there are **no dangling paths**.

| Assertion | Code path | Test path | **Evidence keys** | CI gate |
| --- | --- | --- | --- | --- |
| Registry package surface is a thin re-export of bridge types | `lirix/registry/__init__.py` | *(n/a — no logic)* | **仅内部桥接，不变量由 `bridges.py` 与下游测试 / gate 覆盖** | `python tools/harness.py registry-authority-contract`（间接：导出面不得漂移） |
| Bridge registry routes resolve fail-closed for unknown protocol/chain | `lirix/registry/bridges.py` | `tests/test_registry/test_bridges.py`, `tests/test_v1_3_0_cross_chain.py`, `tests/test_core/test_registry_authority_contract.py` | `exception.error_code` (`LRX_BRIDGE_*`), `context.protocol`, `context.src_chain` | Registry authority contract gate + mainline pytest |
| Intents package exports a single translator entrypoint | `lirix/intents/__init__.py` | *(n/a — no logic)* | **仅内部桥接；** 对外稳定意图翻译在 **`translator.py`**；不变量由 translator + registry 测试覆盖 | Mainline pytest |
| Bridge intent translator delegates routing invariants to the registry + calldata builder | `lirix/intents/translator.py` | `tests/test_intents/test_translator.py` | same bridge resolution errors; calldata `data` / `to` on success | Mainline pytest (`coverage_required` / full local suite) |
| Audit package re-exports `AuditLogger` for ergonomic imports | `lirix/audit/__init__.py` | *(n/a — no logic)* | **仅内部桥接**；日志与红化不变量在 **`logger.py`** | Mainline pytest |
| Audit logger emits redacted JSON lines; `HOOK_ON_AUDIT_LOG` receives structured `audit_event` | `lirix/audit/logger.py` | `tests/test_core/test_audit_logger.py`（severity / redaction / nested secrets）, `tests/test_core/test_hook_manager.py`（`HOOK_ON_AUDIT_LOG` 与 `audit_event.attributes`） | `severity_text`, `attributes.*`（含 `lirix.*` 与红化字段）, hook `audit_event` payload | Mainline pytest（治理子集含 hook；全量含审计交互） |

---

## 📤 Top-level API Output Boundary

- **Evidence-emitting entrypoints**: `validate_only`, `async_validate_only`, `simulate_only`, `async_simulate_only`, `validate_and_simulate`, `async_validate_and_simulate`.
- **Assumptions / non-goals**: see `docs/assumption_register.md`.
  - return: `security_trace`, `validation_session`, `agent_feedback`, `migration_modes`, `evidence_schema_version`.

### Non-pipeline helpers

These module-level entrypoints do **not** emit new pipeline `SecurityTrace` / session timeline artifacts on their own:

- `replay_session`
- `resolve_failure_protocol`
- `build_for_chain_profile`

---

## 🏗️ Layout status (implemented)

- **E8**: `Lirix` lives in [`lirix/_facade.py`](../lirix/_facade.py); module-level helpers (`replay_session`, `build_for_chain_profile`, …) ship from [`lirix/_client_facade.py`](../lirix/_client_facade.py) and are re-exported via [`lirix/__init__.py`](../lirix/__init__.py), which also holds the Python version gate and a **narrow** `__all__`.

## 🔗 Internal pipeline composition (contributor note)

- **本地跑 `python tools/harness.py <subcommand>` 前**：先查 **`docs/tools_gates_index.md`**（依赖、`pip install -e`、典型退出码），避免与 CI 步骤假设不一致。
- **`ClientPipelineProtocol`** in [`lirix/core/client_components.py`](../lirix/core/client_components.py) is the **internal** composition surface used by `Lirix` in [`lirix/_facade.py`](../lirix/_facade.py). Treat it as a stability boundary for **in-repo** refactors, not as a semver-bound extension point for `from lirix import ...` consumers.
- [`lirix/core/pipeline_protocol.py`](../lirix/core/pipeline_protocol.py) is a **backward-compatible re-export** of selected helpers only; **new code should import from** `lirix.core.client_components` (or tighter modules) rather than growing new coupling through `pipeline_protocol`.

---

## 🧭 Optional follow-ups (non-blocking)

- **R2 (removed parse helper)**: `lirix.legacy` / `lirix.core.guard` deleted; canonical entry is [`from lirix import Lirix`](../lirix/__init__.py) with implementation [`lirix/_facade.py`](../lirix/_facade.py) (single orchestrated DAG).

---

## Session gate semantics (l1_l3_ok)

**Single authoritative definition.** **Normative rule for docs:** define timing, consumers, and re-check behavior **only in this section**. Other documents (`README`, `docs/pipeline_evidence_flow.md`, `docs/architecture_control_plane.md`, `docs/api_reference.md`, `docs/quickstart.md`, `docs/release_notes.md`) must **link here** instead of restating gate logic, so wording cannot drift.

### Field and consumers

- **Field:** `ValidationSession.state["l1_l3_ok"]` (bool), written only by **`Lirix._mark_session_l1_l3_ok`** (via orchestrator paths).
- **Consumers:** when **`LirixConfig.simulate_only_requires_prior_validate`** is **true**, `simulate_only` / `async_simulate_only` require this flag on the **same** session before entering L4/L5. **`simulate_only` does not run the full pipeline’s post–`HOOK_PRE_SIMULATION` L1–L3 re-check**; that re-check exists **only** in `LirixPipelineOrchestrator.run_full`.

### Meaning (one sentence)

**`l1_l3_ok` means “initial L1–L3 validation succeeded and the runtime marked the session gate”** — not “simulate_only ran”, not “full pipeline completed”, not “post–`HOOK_PRE_SIMULATION` re-check succeeded”.

### When the flag is set (by entrypoint)

- **`validate_only` / `async_validate_only`:** set **after** isolated **`HOOK_POST_VALIDATE`** completes successfully (same `run_validate` path as today).
- **`validate_and_simulate` / `async_validate_and_simulate`:** set **after** the **first** successful **`_run_l1_l3_validation`** and **before** **`HOOK_PRE_SIMULATION`**, on the **same** normalized `draft_payload` produced by `request_normalization` for that call.

### Full pipeline: second L1–L3 pass (re-check)

- **Where:** `LirixPipelineOrchestrator.run_full` — immediately **after** **`HOOK_PRE_SIMULATION`** (and its fatal hook aggregate), **before** **`_build_rpc_manager()`** / L4.
- **Payload:** the **same** in-memory `draft` mapping (no second normalization pass).
- **Role:** fail-closed **re-validation** after hooks that may observe or transform perimeter policy; **does not** set or clear **`l1_l3_ok`**.
- **On re-check failure:** raises **`LirixBaseException`**; **`_record_failure`** records rejected **`validation_session.timeline`** entry, blocked **decision**, and **enriched** `exception.context` (`agent_feedback`, `failure_protocol`, bundles). **L4/L5 and post-simulation / post-validate hooks do not run.** **`l1_l3_ok` is not cleared** by design — the gate still reflects **initial** L1–L3 success; callers must not infer “safe to broadcast” from this flag alone after a failed full pipeline.

### `simulate_only_requires_prior_validate`

- Requires prior L1–L3 success on the session so a later **`simulate_only`** can run; it does **not** require a completed successful **`validate_only`** hook closure when the prior attempt was a **partial** full pipeline (see **`HOOK_POST_VALIDATE`** note below).

### Versus end-of-pipeline `HOOK_POST_VALIDATE` (full pipeline)

- Trailing **`HOOK_POST_VALIDATE`** (after L5) may **not** run if an earlier stage fails. That is **not** equivalent to a completed successful **`validate_only`**; do **not** infer hook parity from **`l1_l3_ok`** alone.

---

## 🔑 Canonical Audit Join Keys

- `security_trace.correlation_id`: primary pipeline join key
- `validation_session.session_id`: multi-turn orchestration join key
- `replay_bundle.bundle_digest`: replay package identity
- `replay_bundle.registry_closure_digest`: closure anchor for config + registries

---

## ⚙️ CI Enforcement

- Governance gate lives in `.github/workflows/ci.yml` under `Governance gate (explicit)`.
- **Governance lane** (`.github/workflows/governance-lane.yml`, push to `main` / schedule / `workflow_dispatch`) runs **`python tools/cv_score_report.py`** without `--enforce` for CV 制品留痕；主线 PR 合并仍以 `ci.yml` 为准（见 **`docs/ci_gate_matrix.md`**）。
- Full `pytest` + coverage runs after governance gate passes (non-PR job: **`python tools/harness.py test-coverage-required`**).
- **Editing this file’s § Core Assertions Map:** run `python tools/harness.py contract-manifest` before pushing (CI runs it under “Docs contract gate”).
- **`from lirix import` surface:** CI runs `python tools/harness.py root-import-surface` after internal doc link checks (scans `tests/`, `examples/`, `tools/`).
- **Import topology artifact:** regenerate with `python tools/gen_lirix_import_graph.py` (writes `docs/lirix_import_topology.md`).

---

# Audit Path Map / 审计路径地图

This document is the single entrypoint for auditing Lirix's control-plane claims.
It provides a one-hop mapping from **architecture assertions → code symbols → tests → evidence keys → CI gate**.

本文档是 Lirix “控制面可审计性”的**唯一入口**：从 **架构断言 → 代码符号 → 测试 → 证据键 → CI 门禁**，一跳定位。

## 🔗 One-hop Index / 一跳索引

- **Architecture assertions (table)**: `docs/architecture_control_plane.md`
- **Checklist closure matrix**: `docs/checklist_implementation_matrix.md`
- **API contract & stable payload keys**: `docs/api_reference.md`
- **Evidence v2 schema**: [`docs/evidence_schema_v2.md`](evidence_schema_v2.md)
- **Migration guidance (legacy → v2)**: `docs/migration_legacy_to_v2.md`
- **Release delta (additive compatibility)**: `docs/release_notes.md`

## 🔑 Canonical Audit Join Keys / 审计关联主键（Join Keys）

Use these keys to join logs, test artifacts, and replay bundles deterministically:

- **`security_trace.correlation_id`**: primary join key across the whole pipeline.
- **`validation_session.session_id`**: join key across a multi-turn orchestrated workflow.
- **`replay_bundle.bundle_digest`**: replay package identity.
- **`replay_bundle.registry_closure_digest`**: closure anchor that binds config + registries for replay provability.

## 🎯 Control-Plane Assertions → Code → Tests → Evidence Keys

The canonical table lives in `docs/architecture_control_plane.md`. This section explains how to *use* it:

1. Pick an **Assertion** row (what must be true).
2. Jump to the referenced **Code Path** symbol(s) (where enforced).
3. Run/read the referenced **Test Path** (how it is proven).
4. Verify the listed **Evidence Key** exists in returned payloads (`security_trace`, `validation_session`, `replay_bundle`, `forensic_bundle`).

中文用法同理：

1. 先选一条 **架构断言**（必须成立的事实）。
2. 跳到对应的 **代码落点**（在哪里被强制执行）。
3. 查看/运行对应的 **测试用例**（如何被证明）。
4. 用 **证据键** 在返回对象里做字段级核对（`security_trace` / `validation_session` / `replay_bundle` / `forensic_bundle`）。

## 🛡️ CI Governance Gate / CI 治理门禁

The repo uses tests as explicit governance gates. The minimum contract is:

- critical control-plane assertions must have **direct tests** (not just integration smoke)
- additive compatibility is enforced by **payload-key stability** and **export contract** tests

入口提示：

- 若你在本地审计：先跑 `pytest`，再对照 `docs/architecture_control_plane.md` 的断言表逐条抽样核对 evidence keys。
- 若你在做发布审计：以 `docs/release_notes.md` 的 “API Contract Delta” 为变更清单，再用对应测试与 evidence keys 做字段级回归。

## 📚 Where each doc fits / 文档分工（避免多入口漂移）

| Layer | Doc | Role |
| --- | --- | --- |
| Navigation | **`README.md`** | Entry guide: value prop, install, quickstart, links only — not contract SSOT. |
| Audit index | **`docs/audit_path_map.md`** (this file) | Sole audit entry: assertions → code → tests → evidence → CI; **`l1_l3_ok` / revalidation** normative text in § Session gate semantics. |
| Control plane | **`docs/architecture_control_plane.md`** | Assertion table + evidence-key join only; links here for gate semantics. |
| API contract | **`docs/api_reference.md`** | Stable caller contract (keys, compatibility, entry paths). |
| Evidence schema | **`docs/evidence_schema_v2.md`** | v2 evidence envelope (`rpc_evidence_mode=v2_only`; aliases input-only). |
| Migration | **`docs/migration_legacy_to_v2.md`** | Legacy → v2 order and risk controls. |
| Release checklist | **`docs/checklist_implementation_matrix.md`** | Sign-off matrix (assertions → code). |
| Release delta | **`docs/release_notes.md`** | Version-visible deltas; maps to tests and evidence keys. |
| Exclusions | **`docs/repo_exclusions.md`** | Exclusion boundary SSOT (`.gitignore`, `.harnessignore`, pytest `norecursedirs`). |

---

## 历史决策与演进计划 / Historical decisions & evolution

**EN:** Deep-dive and planning docs that are not repeated in the core assertion table above; link them here so the audit map stays the one-hop index.

**中文：** 下列深度文档未在上文断言表中重复展开；在此显式挂链，避免「文档孤岛」。

- [`adr_0002_ci_fast_required_minset_and_governance_lane.md`](adr_0002_ci_fast_required_minset_and_governance_lane.md) — Fast Required 与 governance lane 的 ADR。
- [`major_hard_removal_plan.md`](major_hard_removal_plan.md) — 硬移除与收敛计划。
- [`migration_observability_dashboard.md`](migration_observability_dashboard.md) — 迁移可观测看板说明（与 `tools/migration_observability_report.py` 产出配套）。
