# Lirix Project Structure
# Lirix 项目结构

```text
lirix/
├── lirix/
│   ├── __init__.py                 # EN: Public SDK entrypoint (L1-L5 orchestration). / 中文：SDK 公开入口（编排 L1-L5）。
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
│   └── test_integration/           # EN: End-to-end and Anvil-backed integration tests. / 中文：端到端与 Anvil 集成测试。
├── .github/workflows/
│   ├── ci.yml                      # EN: Matrix CI (py38-py314 + Foundry/Anvil). / 中文：矩阵 CI（py38-py314 + Foundry/Anvil）。
│   └── release.yml                 # EN: OIDC-based PyPI + GitHub Release pipeline. / 中文：基于 OIDC 的 PyPI/GitHub Release 流水线。
├── docs/
│   └── STRUCTURE.md
├── SECURITY.md
├── CONTRIBUTING.md
└── pyproject.toml
```

## Safety Notes
## 安全说明

- `l1_intent_validator.py` is the first barrier; if intent is ambiguous, execution must stop.
- `multicall.py` must never hide nested call targets from the security pipeline.
- `hook_manager.py` must remain non-invasive: hooks extend behavior, but never bypass the core defense layers.

- `l1_intent_validator.py` 是第一道屏障；只要意图存在歧义，执行就必须停止。
- `multicall.py` 绝不能将嵌套调用目标隐藏在安全流水线之外。
- `hook_manager.py` 必须保持无侵入：Hook 只能扩展行为，不能绕过核心防线。
