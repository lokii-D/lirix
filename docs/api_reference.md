# API Reference / API 参考

## 中文

以下为高层入口，完整签名以源码与类型标注为准。

| 符号 | 说明 |
| ---- | ---- |
| `Lirix` | 主入口：挂载 `HookManager`、`AuditLogger`，提供 `chain_validate` 与模拟路径。 |
| `LirixConfig` | Pydantic 冻结配置；初始化时完成地址规范化与约束检查。 |
| `atomic_multicall` | 将多笔子调用编码为 Multicall3 单笔 calldata，并走 L1–L3 校验；**不签名、不广播**。 |
| `register_hook` | 在 `HookManager` 上注册钩子（与 `HookManager.register_hook` 等价）。 |
| `HookManager` | 同步/异步钩子调度、隔离超时、审计绑定。 |
| `IntentValidator` / `SchemaValidator` / `DeFiPayloadParser` | L1 / L2 / L3 分层校验（亦可通过 `Lirix.chain_validate` 串联）。 |
| `RPCManager` / `SandboxSimulator` | L4 / L5：RPC 协调与 `eth_call` 沙盒模拟（需有效 RPC 配置）。 |

异常类型均继承自 `LirixSecurityException`（见 `lirix.core.exceptions`）。

---

## English

High-level entry points (see source for full signatures):

| Symbol | Role |
| ------ | ---- |
| `Lirix` | Main facade: hooks, audit, `chain_validate`, simulation helpers. |
| `LirixConfig` | Frozen Pydantic configuration with address normalization. |
| `atomic_multicall` | Encode Multicall3 calldata and run L1–L3 checks; **does not sign or broadcast**. |
| `register_hook` | Register hooks on `HookManager`. |
| `HookManager` | Sync/async hook dispatch with timeouts and audit integration. |
| Layer validators / `RPCManager` / `SandboxSimulator` | L1–L5 pipeline as implemented under `lirix.layers`. |

All security-related failures use subclasses of `LirixSecurityException`.
