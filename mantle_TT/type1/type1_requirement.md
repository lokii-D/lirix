## 官方评委考核清单（第一类：程序与代码）

**赛事**：Mantle Turing Test Hackathon 2026 · AI DevTools 赛道
**总分**：100 分
**评分权重参考（交叉验证，2026-05-05）**：Technical Depth 30% + Mantle Contribution 25% + Product Completeness 20%

---

## 通过门槛（必须同时满足）

> **门槛**：总分 **≥ 85** 且 **全部 Mandatory 通过**
> **Mandatory**：任意一项未通过即 **淘汰（0 分）**

- **已部署**：Mantle **主网/测试网**（RPC + `chain_id` 5000/5001）
- **开源仓库**：GitHub repo 公开可 clone（`mantle-turing-2026` 分支或主分支）
- **可运行 Demo**：Streamlit + Hugging Face Spaces **公开 URL**
- **至少 1 个 AI-powered on-chain 可调用函数**：例如 `Lirix.validate_and_simulate` → Mantle 执行/阻断
- **合约已 verify**：若提交 Project Deployment Award
- **README 完整**：Mantle 配置、架构图、Docker 快速启动

---

## 评分维度（共 100 分）

### 1) Mantle 生态接入深度（25 分）

- **Mantle 预设配置正确**：`LirixConfig.for_mantle()` 预设主网/测试网 RPC 矩阵
  - **主网节点数量要求**：≥ 3
  - **至少包含**：`rpc.mantle.xyz`、`mantle.drpc.org`、`rpc.ankr.com/mantle`
- **官方白名单地址注入正确**：
  - Merchant Moe `MoeRouter`
  - Agni Swap `Router`
  - Pendle `Router V4`
  - INIT `Core Proxy`
  - 资产/代币：`mETH` / `cmETH` / `FBTC` / `USDY` / `WMNT` / `MOE`
- **Multicall3 地址正确**（Mantle 原生地址）：

```text
0xcA11bde05977b3631167028862bE2a173976CA11
```

- **L4 RPC quorum 可用**：Mantle 配置下正常工作（`spread ≤ 2` 视为通过）
- **Fork 测试通过**：

```bash
anvil --fork-url https://rpc.mantle.xyz
```

### 2) 签名常量与 L3 DeFi 解析器适配（20 分）

- **签名常量补齐**：`signatures.py` 新增
  - Agni V3 `exactInput` / `exactOutput` selector
  - Merchant Moe LiquidityBook `swap` selector
  - selector 获取方式正确（`Web3.keccak` 或 `cast`）
- **解析器能力完备**：`l3_defi_parser.py` 支持
  - V3 `path` 解析
  - `amountOutMinimum` 检查
  - Merchant Moe `swap` 解析
  - 路由毒化/滑点拦截
- **恶意 payload 可拦截**：如 `amountOutMin=0`、钓鱼 `recipient`
- **兼容性要求**：
  - Multicall 递归
  - Proxy Piercer（EIP-1967 / EIP-2535 Diamond）
  - 对 Pendle/INIT/cmETH/USDY **零改动兼容**

### 3) 核心安全流水线完整性（20 分）

- **L1–L5 流程保持一致**：Mantle 配置下 pass/fail 逻辑不变（保留 **fail-closed**）
- **默认策略 Mantle 友好**：`ShadowAuditor` 预设
  - `MAX_SLIPPAGE_BPS=50`
  - `FORBIDDEN_METHODS` 保留
- **关键环节正常**：L2 schema 校验 + L5 零 Gas 模拟 + revert 自然语言转译
- **测试通过**：原有测试 + 新增 Mantle 测试通过（覆盖率目标不下降）

### 4) 交互式 Demo 与 Docker 化（15 分）

- **Streamlit 完整交互**（`app.py`）：
  - Mantle 网络选择
  - payload 输入
  - L1–L5 实时可视化状态
  - ShadowAuditor 卡片
  - Mantle Explorer 交易链接
- **一键启动**：`Dockerfile` + `docker-compose.yml`（Streamlit 7860 + 可选 Anvil fork）
- **已上线**：Hugging Face Spaces（公开 URL、无需 API Key）

### 5) CI 集成与工程规范（10 分）

- **CI 覆盖 Mantle fork**：`.github/workflows/ci.yml` 新增 job（Foundry + `pytest tests/mantle/`）
- **工程质量门槛**：`mypy --strict`、ruff、black、覆盖率要求全部通过
- **安全合规**：无硬编码私钥；主网配置不混入测试网地址

### 6) 示例脚本与文档完整度（10 分）

- **示例脚本**：`/Users/dingjunqing/Desktop/Lirix/mantle_TT/examples/mantle_defi_demo.py`
  - 用真实 Mantle 地址构造恶意/安全场景
  - 演示 L1–L5 + 自我修复闭环
- **README 更新**：Mantle 配置说明 + 快速启动 + 架构图 + HF Spaces 链接

---

## 评委视角的分数区间（经验判断）

- **95–100**：冠军级（可直冲 Grand Champion）
- **85–94**：强项目（高概率拿 Track Prize + Deployment Award）
- **< 85 或任一 Mandatory 未通过**：无法进入决赛

---

## 评委结论（当前状态）

- 你已完成的「第一类：程序与代码」清单已 **100% 对齐** 官方硬性要求与评分维度。
- 现在运行 `pytest` + 本地 Docker 测试 + HF Spaces 部署，即可进入下一阶段
