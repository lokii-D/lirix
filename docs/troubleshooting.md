# Troubleshooting / 故障排除


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).

## 🔍 Operator snapshot

Most “breakages” here are **fail-closed by design**: the SDK refused an ambiguous intent, a mismatched allowlist, or a hostile RPC view. Read the exception, tighten config, rerun—**do not** downgrade security exceptions to warnings in business code.

---

## English

### Version errors

Use Python 3.9–3.14 as enforced by `lirix/__init__.py` until support is officially extended.

### Validation exceptions

These usually mean fail-closed behavior. Re-check allowlists, `chain_id`, and that calldata matches declared functions.

### Skipped Anvil tests

Start Anvil on `127.0.0.1:8545` or rely on CI, which starts Anvil automatically.

### mypy vs runtime Python

The mypy target version may differ from the minimum runtime; see `[tool.mypy]` in `pyproject.toml`.

### pip vs pip3

Prefer `python -m pip` to target the correct interpreter in multi-Python setups.

### Multi-version testing (tox)

Use **`tox`** with the environments declared under **`[tool.tox]` in `pyproject.toml`** (`legacy_tox_ini`) to run the same checks across Python versions locally; missing interpreters are skipped when `skip_missing_interpreters` is enabled.

### Canonical error codes (`LIRIX_ERR_*`)

These codes appear on exceptions and in evidence envelopes as `canonical_error_code`. Map the code → fix:

| Code | Meaning (short) | What to do |
|------|-----------------|------------|
| `LIRIX_ERR_CIRCUIT_BREAKER_OPEN` | RPC or dependency circuit breaker is open after repeated failures. | Back off, rotate RPC URLs, reduce concurrency; inspect prior errors in the trace. |
| `LIRIX_ERR_INVALID_INTENT` | Intent label or payload does not match allowed intents / required fields. | Align `intent` with config `allowed_intents`; fill required fields per docs and registry. |
| `LIRIX_ERR_CONFIGURATION_GUARD` | Config violates authority / closure / compatibility rules. | Fix `LirixConfig` against `LirixConfig` docs and registry authority gates; remove ambiguous flags. |
| `LIRIX_ERR_HOOK_EXECUTION` | User hook raised or violated hook contract (sync/async mismatch, timeout, etc.). | Fix hook implementation; ensure correct async API; respect hook timeout budgets. |
| `LIRIX_ERR_RPC_UNAVAILABLE` | No healthy RPC endpoint or transport-level failure. | Check `rpc_urls`, network, chain id; verify quorum health and timeouts. |
| `LIRIX_ERR_VALIDATION_FAILED` | Generic validation failure (ABI, args, signatures, bridge rules, etc.). | Read `context["reason"]` / exception message; align calldata, types, and allowlists. |
| `LIRIX_ERR_HOOK_UNKNOWN_POINT` | Hook registered for an unknown hook point string. | Use only documented `HOOK_*` hook points from `lirix.core.constants`. |
| `LIRIX_ERR_HOOK_ASYNC_REQUIRED` | Async hook used where sync context is required (or vice versa per API). | Switch to `ainvoke_*` path or register sync hooks only where required. |
| `LIRIX_ERR_ADDRESS_CHECKSUM` | EIP-55 / address normalization failed. | Pass checksummed or valid hex addresses; reject malformed user input early. |
| `LIRIX_ERR_SCHEMA_VALIDATION` | L2 / envelope schema failed Pydantic or structural validation. | Fix payload shape against schema docs; keep `data` hex within size limits. |
| `LIRIX_ERR_MALICIOUS_PAYLOAD` | Fail-closed interpretation (poisoned routes, unsupported inner calls, decoder errors, etc.). | Treat as hostile or malformed calldata; do not retry blindly; narrow `to` / calldata. |
| `LIRIX_ERR_SIMULATION_FAILED` | Shield / simulation outcome does not satisfy assertions or replay checks. | Inspect simulation trace; adjust slippage, assertions, or chain state assumptions. |
| `LIRIX_ERR_MULTICALL_ENCODING` | Multicall batch encoding or decoding invariant violated. | Verify Multicall3 target, selectors, and nested call policy. |
| `LIRIX_ERR_DEFI_SLIPPAGE_MISSING` | Swap path sets zero min-out (unbounded slippage). | Require non-zero `amountOutMin` / V3 min-out in calldata or reject at policy. |
| `LIRIX_ERR_RPC_QUOTA_EXHAUSTED` | HTTP 429 / quota from provider. | Reduce rate, add backoff, add RPCs, or upgrade provider tier. |
| `LIRIX_ERR_INSUFFICIENT_FEE` | Fee or gas economics fail policy checks. | Adjust gas limit/price strategy or intent to satisfy policy. |
| `LIRIX_ERR_NONCE_DESYNC` | Nonce does not match chain head / policy. | Resync nonce from RPC; avoid parallel sends without queueing. |
| `LIRIX_ERR_CONTRACT_PAUSED` | Target contract reports paused or incompatible state. | Abort or switch route; verify contract operational status on chain. |
| `LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT` | Dual-`approved` broadcast extract failed (`to` / `data` invariant). | Only extract broadcast fields when both `decision` and `status` are `approved`; supply non-empty `to`/`data`. |
| `LIRIX_ERR_RPC_CONSENSUS_FAILED` | Multi-RPC consensus / evidence quorum failed. | Add consistent RPCs; inspect disagreeing responses; widen quorum policy if appropriate. |
| `LIRIX_ERR_RPC_QUORUM_FAILED` | Quorum `eth_call` / height reconciliation failed on selected endpoints. | Same as RPC health: fix URLs, timeouts, and agreement across nodes. |
| `LIRIX_ERR_POLICY_BLOCKED` | Shadow auditor / policy bundle blocked the action. | Relax or update policy only if business-justified; otherwise change payload/route. |
| `LIRIX_ERR_LEGACY_ERROR` | Legacy `LRX_*` or unknown code normalized here. | Upgrade client to native `LIRIX_ERR_*` handling; map legacy codes via `canonicalize_error_code`. |

---

## 中文

**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

### `ImportError: Lirix requires Python 3.9 through 3.14`

使用受支持的解释器版本；勿使用 3.8 或 3.15+（除非项目已正式扩展支持）。

### `ConfigurationGuardException` / `InvalidIntentException` 等

属于 **预期内的失败安全行为**。请核对：

- `chain_id` 与合约地址是否一致；
- `allowed_*` 白名单是否覆盖当前 `to` / `function_name` / intent；
- calldata 是否与声明的函数一致。

### 集成测试跳过（Anvil）

若本地运行 `tests/` 中依赖 Anvil 的用例被跳过，请在 `http://127.0.0.1:8545` 启动 Anvil，或参考 CI 工作流。

### CI：Mantle fork 步骤

GitHub Actions 中 Mantle fork 作业依赖仓库 secret `MANTLE_MAINNET_RPC`。未配置时该步骤会跳过（exit 0），主 CI 仍可通过；需要该路径时请在仓库中配置 secret。

### `mypy` 与 Python 3.9+

仓库内 `mypy` 配置以 `pyproject.toml` 的 `[tool.mypy]` 为准，**运行兼容性**以 `requires-python` 为准。

### `pip` vs `pip3`

在仅安装 Python 3 的环境中，`pip` 与 `pip3` 通常等价；若系统存在多个 Python，请显式使用 `python3 -m pip install ...` 指向目标解释器。

### 本地跨版本测试（tox）

推荐使用 **`tox`**（配置见仓库根目录 **`pyproject.toml`** 中的 **`[tool.tox]`**）在本地对齐 CI 的 Python 3.9–3.14 矩阵：安装 dev 依赖后执行 `tox`；未安装的解释器对应环境会被跳过（`skip_missing_interpreters = true`）。

### 规范错误码（`LIRIX_ERR_*`）

以下与 `lirix/core/constants.py` 中 `Final[str]` 常量一致，并出现在异常的 `canonical_error_code` 与证据负载中。处理顺序建议：**读异常 `context` → 对照下表 → 改配置或载荷**。

| 错误码 | 含义（简述） | 建议处理 |
|--------|--------------|----------|
| `LIRIX_ERR_CIRCUIT_BREAKER_OPEN` | 熔断打开（连续失败后的自我保护）。 | 退避、更换 RPC、降并发；结合 trace 中前置错误排查。 |
| `LIRIX_ERR_INVALID_INTENT` | intent 或字段与允许集合不匹配。 | 对齐 `allowed_intents` 与意图载荷必填字段。 |
| `LIRIX_ERR_CONFIGURATION_GUARD` | 配置违反权威/闭包/兼容策略。 | 按文档修正 `LirixConfig` 与注册表权威约束。 |
| `LIRIX_ERR_HOOK_EXECUTION` | 用户钩子执行失败或违反契约。 | 修正钩子实现、同步/异步用法与超时。 |
| `LIRIX_ERR_RPC_UNAVAILABLE` | 无可用 RPC 或传输失败。 | 检查 `rpc_urls`、网络与 `chain_id`；检查 quorum 健康与超时。 |
| `LIRIX_ERR_VALIDATION_FAILED` | 通用校验失败（ABI、参数、签名、桥等）。 | 根据 `context["reason"]` 调整 calldata、类型与白名单。 |
| `LIRIX_ERR_HOOK_UNKNOWN_POINT` | 未知 hook 点字符串。 | 仅使用 `constants` 中已定义的 `HOOK_*` 钩子点。 |
| `LIRIX_ERR_HOOK_ASYNC_REQUIRED` | 异步钩子在不允许的上下文注册/调用。 | 使用异步 API 路径或改为同步钩子。 |
| `LIRIX_ERR_ADDRESS_CHECKSUM` | 地址规范化 / EIP-55 失败。 | 使用合法 hex 与 checksum 地址；前置校验用户输入。 |
| `LIRIX_ERR_SCHEMA_VALIDATION` | L2 / 信封结构校验失败。 | 对照 schema 文档修正字段与 `data` 长度限制。 |
| `LIRIX_ERR_MALICIOUS_PAYLOAD` | 失败关闭的恶意或畸形载荷（路由投毒、嵌套调用非法等）。 | 勿盲目重试；收紧 `to` 与 calldata 策略。 |
| `LIRIX_ERR_SIMULATION_FAILED` | 仿真或断言未通过。 | 查看仿真 trace；调整滑点、断言或链上状态假设。 |
| `LIRIX_ERR_MULTICALL_ENCODING` | Multicall 编解码不变量被破坏。 | 确认 Multicall3 地址、selector 与嵌套策略。 |
| `LIRIX_ERR_DEFI_SLIPPAGE_MISSING` | 交换路径最小出量为 0。 | 策略上拒绝或要求非零 `amountOutMin`。 |
| `LIRIX_ERR_RPC_QUOTA_EXHAUSTED` | 429 / 配额耗尽。 | 限速、退避、扩容 RPC 或升级服务商。 |
| `LIRIX_ERR_INSUFFICIENT_FEE` | 费用策略不通过。 | 调整 gas 策略或意图以满足策略。 |
| `LIRIX_ERR_NONCE_DESYNC` | nonce 与链上/策略不一致。 | 从 RPC 重同步 nonce；避免无队列的并发发送。 |
| `LIRIX_ERR_CONTRACT_PAUSED` | 合约暂停或状态不兼容。 | 中止或更换路由；链上确认合约状态。 |
| `LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT` | 双 `approved` 下广播字段提取不变量失败。 | 仅在双 approved 时提取；提供非空 `to`/`data`。 |
| `LIRIX_ERR_RPC_CONSENSUS_FAILED` | 多 RPC 共识/证据失败。 | 增加一致节点、检查分歧响应。 |
| `LIRIX_ERR_RPC_QUORUM_FAILED` | Quorum `eth_call` / 高度对齐失败。 | 同 RPC 不可用：修正 URL 与超时。 |
| `LIRIX_ERR_POLICY_BLOCKED` | Shadow / 策略包拦截。 | 业务允许时才放宽策略；否则更换载荷/路径。 |
| `LIRIX_ERR_LEGACY_ERROR` | 遗留 `LRX_*` 或未知码规范化的落点。 | 客户端迁移到 `LIRIX_ERR_*`；使用 `canonicalize_error_code` 对照。 |
