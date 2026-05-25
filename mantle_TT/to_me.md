# Mantle_TT ToMe（最终整合版：提交 / 演示 / 自证）

目标：你只看这一份，就能完成最终提交、现场演示、评审问答，不漏项、不跑偏、不堆废话。

---

## 0) 先记住结论（你现在处于什么状态）

- 你已完成：代码能力、文档包、脚本链路、测试与覆盖率门槛、评审入口结构。
- 你未完成：外部真实证据（GitHub 公链路、HF Spaces、公网 Demo、链上 tx 证明、可选 verify）。
- 风险真相：技术分够强，但 **Mandatory 外证没补齐会被一票否决**。

---

## 1) 这个提交包到底在干什么（给你自己的统一口径）

一句话：把 AI/用户生成的 DeFi 交易请求，在 Mantle 上链前做 L1-L5 分层审计；不安全就拦（fail-closed），并给出可解释原因。

你要强调的价值：
- 防 recipient 钓鱼、白名单外触达、滑点缺失、路由毒化、嵌套 multicall 过深、RPC 状态分叉。
- 不是“AI 玄学判断”，是“calldata 可解析 + 策略可复现 + 测试可验证”。

---

## 2) 评委实际打分模型（你按这个组织呈现）

Mandatory（不过即 0 分）：
- Mantle 主网/测试网接入与可运行能力
- 公共开源仓库可审计
- 可运行 Demo（含公开访问路径）
- 至少 1 个 AI-powered on-chain callable function 真实证明
- （申报部署奖才需要）合约 verify

评分维度（100 分）：
- Mantle 接入深度 25
- 签名常量与 L3 解析适配 20
- L1-L5 安全流水线完整性 20
- 交互 Demo + Docker 15
- CI + 工程规范 10
- 示例脚本 + 文档完整度 10

过线经验值：总分 >=85 且 Mandatory 全过。

---

## 3) 你包内“已完成可自证”清单（可直接给评委看）

### A. Mantle 接入与核心能力
- `LirixConfig.for_mantle()`：chain id / RPC 矩阵 / allowlist / Multicall3 完整。
- `signatures.py`：V2/V3/Moe selector 已纳入。
- `l3_defi_parser.py`：V3 path、滑点校验、multicall 递归安全控制。
- `l3_proxy_piercer.py`：EIP-1967 / EIP-2535 兼容路径。
- `l4_rpc_manager.py`：quorum + spread fail-closed。
- `l5_shadow_auditor.py`：策略门禁（如 slippage、forbidden methods）。

### B. 可运行与可交付
- 评审入口：`mantle_TT/mantle/README.md`（canonical）。
- 主演示：`mantle_TT/examples/mantle_defi_demo.py`（canonical）。
- 交互演示：`mantle_TT/app.py`。
- 打包与校验：`mantle_TT/scripts/validate_bundle.sh`、`mantle_TT/scripts/pack_bundle.sh`。
- 单一来源：`mantle_TT/to_me.md` 为主，`type1/to_me.md` 是软链接。

### C. 工程质量
- 测试：全绿。
- 覆盖率：`lirix` 100%（fail_under=100）。
- 质量门：ruff / black / mypy 串联到 CI。

---

## 4) 你还必须补的东西（只能你补，我不能代替）

- [ ] GitHub 公共仓库 URL（含最终分支和 commit）
- [ ] Hugging Face Spaces 公共 URL（可直接访问）
- [ ] 公共 Demo URL（若有）
- [ ] 至少 1 条真实 on-chain 证据（tx hash + explorer + 简述）
- [ ] （可选）verify 链接（仅部署奖相关）

硬规则：只填真实可验证证据，不写“预期上线/计划中”当完成项。

---

## 5) 最短验收命令（提交前必须全部过）

在仓库根目录执行：

```bash
bash mantle_TT/scripts/validate_bundle.sh
bash mantle_TT/scripts/run_mantle_demo.sh
./.venv/bin/python -m pytest -q
./.venv/bin/python -m coverage erase
./.venv/bin/python -m coverage run -m pytest -q
./.venv/bin/python -m coverage report
bash mantle_TT/scripts/pack_bundle.sh
```

通过标准：
- `validate_bundle.sh` 输出 `bundle-ok`
- demo 输出“恶意拦截 + 修复后通过 + 安全通过”
- `pytest` 全绿
- 覆盖率 100%
- 成功生成 `mantle_TT/dist/mantle_TT_submission_bundle.tar.gz`

---

## 6) 最优展示流程（现场 8-10 分钟）

### 第 1 段（1 分钟）：问题与定位
- 你做的不是钱包，不是交易机器人；你做的是“上链前安全网关”。
- 核心承诺：不确定就拒绝（fail-closed），并能解释为什么拒绝。

### 第 2 段（3 分钟）：跑主 demo
- 运行 `bash mantle_TT/scripts/run_mantle_demo.sh`。
- 指出三幕：恶意被拦 -> 策略修复 -> 安全通过。
- 用“输入 payload -> L1-L5 判定 -> 输出结果”讲逻辑闭环。

### 第 3 段（2 分钟）：证据与质量
- 跑 `validate_bundle.sh` + `pytest` + `coverage report`。
- 说明不是 PPT 项目：代码、测试、脚本、打包一致可复现。

### 第 4 段（2-3 分钟）：评委材料导航
- 指向 `mantle_TT/mantle/README.md`，按顺序看 one-pager / architecture / checklist。
- 最后展示外部真实链接（GitHub、HF、tx hash）。

---

## 7) 提交动作清单（按顺序执行，不要改）

1. 跑第 5 节全部命令并截图关键输出。
2. 补齐第 4 节所有外证链接。
3. 在 `type1/submission.md` 或你的提交表单中填入真实 URL 与 tx 证明。
4. 上传 `mantle_TT/dist/mantle_TT_submission_bundle.tar.gz`。
5. 提交后做一次“公开访问自检”：所有 URL 在未登录状态下可访问。

---

## 8) 快速问答模板（评委常问）

- 问：你怎么证明不是 hardcode？
  - 答：给出 demo 的恶意/安全对照 + 测试集 + coverage + fail-closed 策略逻辑。

- 问：为什么你这个比普通规则引擎强？
  - 答：不是单点规则；是 L1-L5 组合，覆盖 intent/schema/calldata/quorum/policy 全链路。

- 问：链上证据在哪里？
  - 答：直接给 tx hash 与 explorer 链接；无证据不宣称上线。

---

## 9) 红线（不要踩）

- 不要伪造 tx hash / explorer / verify / Spaces 链接。
- 不要在现场切到非 canonical 入口导致叙事分叉。
- 不要临场改配置；只跑已验证脚本链路。

---

## 10) 你的最终一句话版本（开场白）

“Lirix 在 Mantle 上做的是 AI 交易请求的链前安全审计网关：能解析、能拦截、能解释、能复现；现在代码和包已完整，剩余只需补齐公开外部证据完成正式提交。”
