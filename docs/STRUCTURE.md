# Lirix Project Structure / Lirix 项目结构

**EN:** Authoritative tree with inline `EN:` / `中文：` comments; repo-wide section template: [`documentation_styleguide.md`](documentation_styleguide.md).  
**中文：** 树形结构内联 `EN:` / `中文：` 注释；块级双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This tree is the **EVM defense-in-depth layout**: L1 intent → L5 simulation, with a **narrow public hull** (`lirix/__init__.py`) and heavy machinery kept in `core/` + `layers/` for auditability.

```text
lirix/
├── lirix/
│   ├── __init__.py                 # EN: Public SDK entrypoint (narrow exports). / 中文：SDK 公开入口（窄导出）。
│   ├── _client_core/               # EN: Module facades (replay, hooks, chain profile). / 中文：模块级门面（回放、Hook、链 Profile）。
│   ├── _facade.py                  # EN: `Lirix` public class + pipeline hooks. / 中文：`Lirix` 公开类与流水线挂载点。
│   ├── audit/
│   │   ├── __init__.py
│   │   └── logger.py               # EN: Structured audit logs with redaction. / 中文：结构化审计日志与脱敏。
│   ├── core/
│   │   ├── __init__.py
│   │   ├── compat.py               # EN: Runtime compatibility helpers. / 中文：运行时兼容层。
│   │   ├── config.py               # EN: Strongly-typed security configuration. / 中文：强类型安全配置。
│   │   ├── constants.py            # EN: Cross-layer security constants. / 中文：跨层安全常量。
│   │   ├── exceptions.py           # EN: Security-domain exception hierarchy. / 中文：安全域异常体系。
│   │   ├── hook_manager.py         # EN: Isolated hook execution and sandboxing. / 中文：隔离式 Hook 执行与沙箱化。
│   │   ├── multicall.py            # EN: Multicall encoding and selector guards. / 中文：Multicall 编码与选择器防护。
│   │   └── signatures.py           # EN: ABI/method signature definitions. / 中文：ABI/方法签名定义。
│   └── layers/
│       ├── __init__.py
│       ├── l1_intent_validator.py  # EN: Intent firewall against prompt injection. / 中文：意图防火墙，拦截提示词注入。
│       ├── l2_schema_validator.py  # EN: Strict payload schema validation. / 中文：严格负载结构校验。
│       ├── l3_defi_parser.py       # EN: Deep calldata traversal and poison checks. / 中文：深度 calldata 穿透与投毒检测。
│       ├── l4_rpc_manager.py       # EN: Multi-node reconciliation and circuit breaker. / 中文：多节点对账与断路器。
│       └── l5_sandbox_simulator.py # EN: EIP-3155 state-override simulation. / 中文：EIP-3155 状态覆写模拟。
├── tests/
│   ├── test_core/                  # EN: Core primitives and hook/audit behavior. / 中文：核心能力与 Hook/审计行为。
│   ├── test_layers/                # EN: L1-L5 adversarial and fail-closed suites. / 中文：L1-L5 对抗与 fail-closed 套件。
│   ├── test_integration/           # EN: Historical integration suite (kept for compatibility). / 中文：历史集成测试目录（兼容保留）。
│   └── test_integrations/          # EN: Canonical integration/governance integration suites. / 中文：当前集成与治理集成测试目录。
├── .github/workflows/
│   ├── ci.yml                      # EN: Matrix CI (Python 3.9–3.14 + Foundry/Anvil). / 中文：矩阵 CI（Python 3.9–3.14 + Foundry/Anvil）。
│   ├── governance-lane.yml         # EN: Governance-only lane for non-required policy checks. / 中文：治理专用 lane（非 required 策略检查）。
│   ├── slow-lane-schedule.yml      # EN: Scheduled slow-lane checks. / 中文：定时慢速 lane 检查。
│   ├── mantle_fork_smoke.yml       # EN: Optional Mantle fork tests (manual dispatch + secret). / 中文：可选 Mantle fork 测试（手动触发 + 密钥）。
│   ├── e2e-anvil-optional.yml      # EN: Optional Anvil e2e lane. / 中文：可选 Anvil 端到端 lane。
│   ├── sbom-optional.yml           # EN: Optional SBOM generation lane. / 中文：可选 SBOM 生成 lane。
│   └── release.yml                 # EN: On GitHub Release published: OIDC PyPI + attach dist to that release. / 中文：Release 发布时 OIDC 发 PyPI 并把 dist 挂到该 Release。
├── docs/                           # EN: Doc hub (audit SSOT + guides). / 中文：文档枢纽（审计 SSOT + 指南）。
│   ├── STRUCTURE.md                # EN: This file — repo + `docs/` topology. / 中文：本文件 — 仓库与 `docs/` 拓扑。
│   ├── 入门与参考 / Onboarding & reference
│   │   ├── quickstart.md
│   │   ├── api_reference.md
│   │   ├── troubleshooting.md
│   │   ├── best_practices.md
│   │   └── contributing_local_tests.md
│   ├── 架构与控制面 / Architecture & control plane
│   │   ├── audit_path_map.md       # EN: Audit SSOT index. / 中文：审计主索引（SSOT）。
│   │   ├── architecture_control_plane.md
│   │   ├── pipeline_evidence_flow.md
│   │   ├── checklist_implementation_matrix.md
│   │   ├── assumption_register.md
│   │   └── supported_tx_shapes.md
│   ├── 证据与策略 schema / Evidence & policy schema
│   │   ├── evidence_schema_v2.md
│   │   ├── provenance_spec.md
│   │   └── policy_lifecycle_and_rollback.md
│   ├── 迁移与可观测 / Migration & observability
│   │   ├── migration_legacy_to_v2.md
│   │   ├── migration_observability_dashboard.md
│   │   ├── migration_observability_scan_policy.md
│   │   └── lirix_import_topology.md  # EN: Generated graph artifact. / 中文：导入图生成物。
│   ├── 治理与 CI / Governance & CI
│   │   ├── ci_gate_matrix.md
│   │   ├── ci_gate_responsibility_matrix.md
│   │   ├── branch_protection_required_checks.md
│   │   ├── tools_gates_index.md
│   │   ├── release_pr_checklist.md
│   │   └── repo_exclusions.md
│   ├── 历史 ADR 与演进 / ADRs & evolution
│   │   ├── adr_0001_architecture_convergence_baseline.md
│   │   ├── adr_0002_ci_fast_required_minset_and_governance_lane.md
│   │   ├── adr_responsibility_boundaries.md
│   │   ├── architecture_evolution_action_list.md
│   │   ├── major_hard_removal_plan.md
│   │   └── legacy_sunset_milestones.md
│   ├── 发布与体例 / Release & style
│   │   ├── release_notes.md
│   │   ├── documentation_styleguide.md
│   │   ├── sbom_optional.md
│   │   └── cv_rubric.yaml
│   ├── baselines/                  # EN: Frozen JSON baselines. / 中文：冻结 JSON 基线。
│   └── *.json                      # EN: Machine contracts (phase exit, metrics, triage). / 中文：机读契约 JSON。
├── examples/
│   ├── basic_usage.py                # EN: Minimal SDK walkthrough. / 中文：最小 SDK 演示。
│   └── validate_and_simulate_broadcast.py  # EN: End-to-end broadcast handoff example with strict dual-approved extract semantics. / 中文：带严格双 approved 提取语义的端到端广播交接示例。
├── SECURITY.md
├── CONTRIBUTING.md
└── pyproject.toml
```

## 🏗️ CI note / CI 说明

- **EN:** PR CI (`.github/workflows/ci.yml`) is split into **Fast Required** (deterministic gates + explicit contract tests) and a small **PR Compatibility Smoke** matrix (py3.9/py3.14). The full coverage suite (**fail_under=100**) runs on `push/main` / `workflow_dispatch` as **Coverage Required (Single Authority)**, keeping PR feedback fast while main remains fail-closed.
- **中文：** PR 门禁（`.github/workflows/ci.yml`）采用 **快/慢分离**：PR 必跑 `Fast Required`（确定性 gate + 明确合同测试集）与小型 `PR Compatibility Smoke`（py3.9/py3.14）；全量覆盖（`fail_under=100`）下沉到 `push/main` / `workflow_dispatch` 的 `Coverage Required (Single Authority)`，保证 PR 反馈速度，同时主干质量保持 fail-closed。

## 🛡️ Safety Notes / 安全说明

Public entrypoints are intentionally narrow: `Lirix`, the three core validation/simulation methods, `replay_session`, `resolve_failure_protocol`, and the minimal compatibility helpers re-exported from `lirix/__init__.py`. Core evidence, governance, and layer implementations remain under their respective packages so the stable surface stays small and auditable.


- `l1_intent_validator.py` is the first barrier; if intent is ambiguous, execution must stop.
- `multicall.py` must never hide nested call targets from the security pipeline.
- `hook_manager.py` must remain non-invasive: hooks extend behavior, but never bypass the core defense layers.

- `l1_intent_validator.py` 是第一道屏障；只要意图存在歧义，执行就必须停止。
- `multicall.py` 绝不能将嵌套调用目标隐藏在安全流水线之外。
- `hook_manager.py` 必须保持无侵入：Hook 只能扩展行为，不能绕过核心防线。
