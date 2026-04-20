# Contributing to Lirix
# 贡献 Lirix

Lirix is a security-first system. Contributions are welcome only when they preserve determinism, preserve the Zero-Key boundary, and improve the developer experience without weakening the trust model.
Lirix 是一个安全优先的系统。只有在不破坏确定性、不突破零密钥边界、且在不削弱信任模型的前提下，贡献才会被接受。

---

## The 120-Point Standard
## 120 分交付标准

Every pull request must satisfy the following baseline before review:

- `black` passes with no formatting drift.
- `ruff check` passes with zero lint violations.
- `mypy` passes in strict mode.
- Test coverage must not drop below 100%.
- Changes must not introduce private-key handling, telemetry, or implicit unsafe fallbacks.
- **Red-Blue Confrontation Testing**: Any PR modifying the L1-L5 defense layers MUST include a corresponding malicious payload in the test suite to prove the interception (Fail-Closed). No PoC, No Merge.
- **No Stealth Architecture Changes**: Any change touching L1-L5 defense logic, adding new hook points, or introducing new dependencies MUST first be proposed via a lightweight ADR for community review. The core security architecture is sacred and cannot be altered “while you’re here”.

任何 Pull Request 在进入评审前，都必须满足以下基线：

- `black` 必须通过，且不得存在格式漂移。
- `ruff check` 必须通过，且不得有任何 lint 违规。
- `mypy` 必须以 strict 模式通过。
- 单测覆盖率绝不允许低于 100%。
- 变更不得引入私钥处理、遥测，或任何隐式的不安全回退。
- **红蓝对抗测试**：任何修改 L1-L5 防线的 PR，必须在测试集中包含对应的恶意 Payload，以证明其拦截能力（Fail-Closed）。没有概念验证，直接拒绝合并。
- **禁止隐式架构变更**：任何触及 L1-L5 防线逻辑、增加新的 Hook 点位或引入新依赖的变更，必须先提交一个轻量级 ADR 供社区评审。核心安全架构是神圣的，不接受“顺手一起改”。

If a PR fails any of these checks, it is not ready. Security debt is still debt.
如果 PR 未能满足上述任一标准，就说明它还没有准备好。安全债务，依然是债务。

---

## One-Command Local Build
## 一键本地构建

Use the following commands to boot a full local development environment, including the toolchain required for L5 sandboxed integration tests.
使用以下命令启动完整的本地开发环境，其中包含 L5 沙盒集成测试所需的工具链。

```bash
# 1. Install Foundry (Required for L5 Sandboxed Integration Tests)
curl -L https://foundry.paradigm.xyz | bash
foundryup

# 2. Install Lirix with dev dependencies
pip install -e ".[dev]"

# 3. Run the 120-Point Test Suite
tox

# 4. Install pre-commit hooks (required before any PR)
pre-commit install
```

If your workflow runs the L5 path directly, keep Anvil active and ensure it is reachable by the test harness.
如果你的工作流会直接运行 L5 路径，请保持 Anvil 运行中，并确保测试框架可以访问它。

Any code that does not pass local `pre-commit` (including `ruff`, `black`, and `mypy`) is not allowed into a pull request.
任何未通过本地 `pre-commit`（包含 `ruff`、`black` 和 `mypy`）的代码，严禁提交 PR。

---

## Local Development Setup
## 本地开发环境搭建

1. Create and activate a Python virtual environment.
2. Install the development dependencies.
3. Install Foundry and start Anvil if you need to run L5 integration tests.
4. Run the formatting, linting, typing, and test suite locally before opening a PR.
5. Install and run `pre-commit` before committing changes.

1. 创建并激活 Python 虚拟环境。
2. 安装开发依赖。
3. 如果你需要运行 L5 集成测试，必须安装 Foundry 并启动 Anvil。
4. 在提交 PR 之前，先在本地执行格式化、lint、类型检查与测试套件。
5. 在提交变更之前，必须安装并运行 `pre-commit`。

Example setup:
示例环境搭建：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

curl -L https://foundry.paradigm.xyz | bash
foundryup
anvil

pre-commit install
pre-commit run --all-files
```

Recommended validation commands:
推荐的验证命令：

```bash
black .
ruff check .
mypy .
pytest --cov
```

For the L5 integration path, keep Anvil running in a separate terminal or as a background process, and ensure the configured RPC endpoint points to the local node expected by the test harness.
对于 L5 集成路径，请将 Anvil 保持在单独终端或后台进程中运行，并确保配置的 RPC 端点指向测试框架预期的本地节点。

---

## ADR Policy
## ADR 规范

Any change affecting core defense logic, hook insertion points, or dependency boundaries requires a lightweight ADR before implementation.
任何影响核心防线逻辑、Hook 插入点或依赖边界的变更，在实现前都需要一份轻量级 ADR。

The rule is simple:
规则很简单：

- No ADR, no architecture change.
- No stealth refactor, no silent dependency addition.
- No security boundary changes without public discussion.

- 没有 ADR，就没有架构变更。
- 没有隐式重构，就没有静默依赖新增。
- 没有公开讨论，就不能更改安全边界。

---

## Pull Request Expectations
## Pull Request 预期

- Keep changes small, explicit, and reviewable.
- Add or update tests whenever behavior changes.
- Document any new security assumptions.
- Preserve the bilingual tone in user-facing documentation when touching docs.

- 保持变更小而明确，便于审查。
- 当行为发生变化时，必须补充或更新测试。
- 记录任何新增的安全假设。
- 修改文档时，请保持面向用户内容的双语风格一致。

---

## What We Do Not Accept
## 我们不接受什么

- Private key handling inside the library.
- Hidden telemetry or analytics collection.
- Non-deterministic safety checks.
- Relaxed typing or test shortcuts that weaken guarantees.

- 在库内部处理私钥。
- 隐藏式遥测或分析数据采集。
- 非确定性的安全校验。
- 会削弱保障的宽松类型检查或测试捷径。
