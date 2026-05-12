# Best Practices / 最佳实践


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).

## 🛡️ Operator snapshot

Lirix hardens the **hand-off surface** between agents, RPC, and calldata. It is not a wallet, not a signer, and not a substitute for protocol audits—treat it as a **deterministic policy engine** around what you were already going to broadcast.

---

## English

1. **Keys**: Keep signing outside Lirix; pass only calldata / structured payloads.
2. **Allowlists**: Minimize `allowed_to_addresses`, `allowed_function_names`, and `allowed_intents`; understand `strict_mode` from code/tests.
3. **RPC**: Use trusted endpoints; Lirix cannot fix a hostile network.
4. **Hooks**: Match the supported callback signatures; avoid untrusted or blocking work inside hooks.
5. **Audit streams**: Protect destinations of `AuditLogger` in production.
6. **Expectations**: Validation and simulation are aids, not a substitute for protocol audits or operational security.

---

## 中文

**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

1. **私钥与签名**：在钱包、硬件模块或独立签名服务中完成；勿传入 Lirix。
2. **白名单**：为 `allowed_to_addresses`、`allowed_function_names`、`allowed_intents` 设定最小权限集合；`strict_mode` 行为请阅读 `LirixConfig` 与测试用例。
3. **RPC**：仅向可信节点暴露；Lirix 不会「隐藏」恶意 RPC 行为，仍需网络层防护。
4. **钩子**：`HookManager` 回调须匹配 `def f(*args, **kwargs)` / `async def f(*args, **kwargs)`；避免在钩子中执行长时间阻塞或不可信代码。
5. **审计**：`AuditLogger` 输出可定向到受控流；生产环境请限制日志访问权限。
6. **期望管理**：本库提供校验与沙盒模拟辅助，**不保证**链上结果或第三方合约无漏洞；上线前请自行审计与测试。
