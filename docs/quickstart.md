# Quickstart / 快速开始


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).

## ⚡ Operator snapshot

Lirix is an **EVM-grade airlock**: calldata and intent enter; either structured evidence leaves, or the call **fails closed**. **Zero keys in-library.** Treat security exceptions as telemetry you act on, not noise to swallow.

- **Ship fast:** install (`bash` blocks below), then prove intent with `validate_only` or the full stack via `validate_and_simulate`.
- **Ship safe:** minimize allowlists, keep signing out-of-process, align imports with **`docs/migration_legacy_to_v2.md`** (root export policy).
- **Roll governance:** `hook_contract_mode` from shadow → enforce; keep single-stack targets explicit—alias labels are migration-only coercion shims.

---

## English

### Install

```bash
pip install lirix
```

Editable install for development:

```bash
pip install -e ".[dev]"
```

### Security notice (required reading)

- **Zero private keys in-library**: Lirix does not accept, store, or process private keys or mnemonics; signing and broadcasting stay in your application.
- **Fail-closed**: validation failures raise exceptions; do not swallow security exceptions in business code.
- **No telemetry**: the SDK does not send usage analytics to third parties.

Runtime dependencies are listed in `pyproject.toml` (e.g. `web3`, `eth-abi`, `pydantic`). This project does **not** claim to be dependency-free at runtime.

### Minimal example

```python
from lirix import Lirix, LirixConfig
from web3 import Web3

cfg = LirixConfig(
    chain_id=1,
    strict_mode=False,
    rpc_urls=[],
    allowed_intents=["swap"],
    allowed_function_names=["swapExactTokensForTokens"],
    allowed_to_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
    ],
    whitelisted_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    ],
    blacklisted_addresses=[],
)
client = Lirix(cfg)
_ = client.validate_only(
    "swap",
    {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x...",  # replace with real calldata from tests or tooling
    },
)
```

Further samples live under `examples/`.

### Layer types (L4/L5)

The root package re-exports **`HookManager`**, **`RPCManager`**, **`SandboxSimulator`**, and **`ProxyPiercer`** for quickstarts; deeper compositors (`ShadowAuditor`, `ShadowPolicySchema`, …) remain **`from lirix.layers import …`**.

```python
from lirix import HookManager, ProxyPiercer, RPCManager, SandboxSimulator
```

See **`docs/migration_legacy_to_v2.md`** (Root export policy).

### Entry Path Matrix

- `validate_only`: L1-L3 validation only.
- `simulate_only`: L4-L5 simulation facts only.
- `validate_and_simulate`: **`docs/pipeline_evidence_flow.md`** · [`l1_l3_ok` SSOT](audit_path_map.md#session-gate-semantics-l1_l3_ok).
- `atomic_multicall`: batch packing with pre-validation.

### LangChain (optional extra)

```bash
pip install lirix[langchain]
# editable install with LangChain extras
pip install -e ".[langchain]"
```

For `lirix.integrations.langchain.LirixSecurityValidator`, install the extra above. Default `optional_deps_mode="best_effort"` suits minimal installs; for production, pass `optional_deps_mode="fail_closed"` so missing `langchain_core` fails at construction time.

### Progressive Migration Flags

Use additive config flags to roll out stricter controls gradually:
`hook_contract_mode`, `policy_lifecycle_mode`, `rpc_evidence_mode`.

Production guidance (does not change defaults):

- Prefer `hook_contract_mode="shadow"` first, then `hook_contract_mode="enforce"` once hooks are stable.
- Treat `hook_contract_mode="legacy"` as migration-only. Do not add new production deployments that rely on legacy hook contract behavior.
- For new integrations, use the single-stack targets (`policy_lifecycle_mode="digest_verified"`, `rpc_evidence_mode="v2_only"`) and avoid alias inputs (`legacy`, `signed_only`, `v2_dual`).

#### Migration-only (deprecated aliases, coercion-only)

State machine (aligned with `docs/migration_legacy_to_v2.md`):

- **Removed**: runtime behavior for `rpc_evidence_mode=legacy|v2_dual` and `policy_lifecycle_mode=legacy`
- **Migrating**: alias inputs (`legacy`, `v2_dual`, `signed_only`) are **coercion-only compatibility shims**
- **Pending removal**: alias input acceptance in the next major release

Hard constraints:

- **Aliases are coercion-only compatibility shims** (accepted to unblock migrations; immediately coerced; do not enable legacy runtime)
  - `rpc_evidence_mode=legacy|v2_dual` → `v2_only`
  - `policy_lifecycle_mode=legacy|signed_only` → `digest_verified`
- **Freeze**: do not add new `legacy` / `v2_dual` / `signed_only` usage
- **Next major**: alias inputs removed (hard removal window)

Example (migration-only; remove ASAP):

```python
cfg = LirixConfig(
    chain_id=1,
    rpc_urls=["https://..."],
    hook_contract_mode="warn",
    policy_lifecycle_mode="legacy",  # coerced → "digest_verified"
    rpc_evidence_mode="v2_dual",     # coerced → "v2_only"
)
```

See: `docs/migration_legacy_to_v2.md` (Single-stack convergence timeline / Migration state machine).

---

## 中文

**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

### 安装

```bash
pip install lirix
# 或
pip3 install lirix
```

开发环境（可编辑安装）：

```bash
pip install -e ".[dev]"
```

### 安全声明（必读）

- **Zero-Key（零私钥）**：本库设计为不接收、不存储、不处理用户私钥或助记词；签名与广播由应用层负责。
- **Fail-Closed**：校验失败时抛出异常并中止；请勿在业务层吞掉安全异常。
- **Zero-Telemetry**：本库不向第三方发送使用统计或遥测数据。

运行时依赖以 `pyproject.toml` 为准（如 `web3`、`eth-abi`、`pydantic`）。本仓库不宣称「零依赖」；若文档其它处出现类似表述，以 `pyproject.toml` 为准。

### 最小示例

```python
from lirix import Lirix, LirixConfig
from web3 import Web3

cfg = LirixConfig(
    chain_id=1,
    strict_mode=False,
    rpc_urls=[],
    allowed_intents=["swap"],
    allowed_function_names=["swapExactTokensForTokens"],
    allowed_to_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
    ],
    whitelisted_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    ],
    blacklisted_addresses=[],
)
client = Lirix(cfg)
# 取证闭环优先用 validate_only；仅需 bool 时可用 chain_validate（内部等价）。
_ = client.validate_only(
    "swap",
    {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x...",  # 实际 calldata
    },
)
```

更多示例见仓库 `examples/` 目录。

### 分层类型（L4/L5 等）

根包为常用流水线类型提供 **`HookManager` / `RPCManager` / `SandboxSimulator` / `ProxyPiercer`** 的 DX 再导出；其余大件（如 `ShadowAuditor`）仍请 **`from lirix.layers import …`**。

```python
from lirix import HookManager, ProxyPiercer, RPCManager, SandboxSimulator
```

详见 **`docs/migration_legacy_to_v2.md`**（Root export policy）。

### LangChain 集成（可选依赖）

```bash
pip install lirix[langchain]
# 开发环境（可编辑安装 + LangChain extras）
pip install -e ".[langchain]"
```

若使用 `lirix.integrations.langchain.LirixSecurityValidator`，请使用上述 extras（安装 `langchain` / `langchain-core`）。**默认 `optional_deps_mode="best_effort"`**：便于无 LangChain 的最小安装或本地测试（内置 stub）。**推荐在生产集成中显式传入 `optional_deps_mode="fail_closed"`**：缺少 `langchain_core` 时在构造阶段抛出 `ConfigurationGuardException`，避免静默分叉。

### 入口路径速览

- `validate_only`：只做结构与语义校验（L1-L3）。
- `simulate_only`：只做 RPC 对账与沙盒模拟（L4-L5）。
- `validate_and_simulate`：**`docs/pipeline_evidence_flow.md`** · [`l1_l3_ok` SSOT](audit_path_map.md#session-gate-semantics-l1_l3_ok)。
- `atomic_multicall`：批量交易打包后统一校验。

### 渐进式迁移开关

```python
cfg = LirixConfig(
    chain_id=1,
    rpc_urls=["https://..."],
    hook_contract_mode="shadow",
    policy_lifecycle_mode="digest_verified",
    rpc_evidence_mode="v2_only",
)
```

这些开关用于**渐进式 rollout**（不改变既有默认值），但对**新集成**的推荐值是 single-stack 目标：

- `policy_lifecycle_mode="digest_verified"`
- `rpc_evidence_mode="v2_only"`

生产环境建议：

- `hook_contract_mode`：优先用 `"shadow"` 观察与留证，稳定后切到 `"enforce"`；`"legacy"` 仅作为迁移期兼容（不要新增依赖 legacy 的生产部署）。
- `policy_lifecycle_mode` / `rpc_evidence_mode`：不要新增 `legacy` / `signed_only` / `v2_dual` 输入；这些标签处于迁移窗口，仅用于下游存量迁移。

#### Migration-only（deprecated aliases, coercion-only）

迁移状态机（与 `docs/migration_legacy_to_v2.md` 一致）：

- **Removed**：`rpc_evidence_mode=legacy|v2_dual`、`policy_lifecycle_mode=legacy` 的旧运行时行为已移除
- **Migrating**：输入 alias（`legacy` / `v2_dual` / `signed_only`）是 **coercion-only compatibility shims**
- **Pending removal**：下个 major 版本移除 alias 输入接受

硬约束（迁移窗口纪律）：

- **Aliases are coercion-only compatibility shims**（仅为兼容输入，**不会**开启旧运行时；会在配置归一阶段立即被 coercion）
  - `rpc_evidence_mode=legacy|v2_dual` → `v2_only`
  - `policy_lifecycle_mode=legacy|signed_only` → `digest_verified`
- **Freeze**：不要新增任何 `legacy` / `v2_dual` / `signed_only` 使用
- **Next major**：移除 alias 输入接受（hard removal）

示例（仅迁移期可用；推荐尽快移除）：

```python
cfg = LirixConfig(
    chain_id=1,
    rpc_urls=["https://..."],
    hook_contract_mode="warn",
    policy_lifecycle_mode="legacy",  # coerced → "digest_verified"
    rpc_evidence_mode="v2_dual",     # coerced → "v2_only"
)
```

迁移细节与权威时间线见：`docs/migration_legacy_to_v2.md`（**Single-stack convergence timeline** / **Migration state machine**）。
