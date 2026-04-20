# Lirix Project Structure
# Lirix 项目结构

```text
lirix/
├── lirix/
│   ├── __init__.py
│   ├── l1_intent_validator.py      # EN: Blocks prompt-injection attempts by enforcing intent boundaries. / 中文：通过意图边界拦截提示词注入攻击。
│   ├── schema.py                   # EN: Enforces strict payload schemas and type safety. / 中文：强制严格的负载结构与类型安全。
│   ├── multicall.py                # EN: Recursively parses nested calldata to expose hidden execution paths. / 中文：递归解析嵌套 calldata，暴露隐藏执行路径。
│   ├── rpc.py                      # EN: Arbitrates RPC state freshness and fail-closed node selection. / 中文：仲裁 RPC 状态新鲜度并执行失败即关闭的节点选择。
│   ├── sandbox.py                  # EN: Runs zero-gas simulations to predict EVM reverts safely. / 中文：运行零 Gas 模拟，安全预测 EVM 回滚。
│   ├── hook_manager.py             # EN: Provides non-invasive extension points for enterprise policy and observability. / 中文：为企业策略与可观测性提供无侵入扩展点。
│   └── exceptions.py               # EN: Defines security-specific failures with precise operator-facing signals. / 中文：定义面向操作者的精确安全异常信号。
├── tests/
│   ├── test_l1_intent_validator.py
│   ├── test_multicall.py
│   ├── test_rpc.py
│   └── test_sandbox.py
├── docs/
│   └── STRUCTURE.md
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
