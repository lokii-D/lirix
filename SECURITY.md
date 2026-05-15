# 🛡️ Security Policy for Lirix

**EN:** Triple-Zero boundary, scope, and private disclosure process. Bilingual Markdown conventions: [`docs/documentation_styleguide.md`](docs/documentation_styleguide.md) (SSOT).
**中文：** 三重零边界、漏洞收录范围与私下报告流程。漏洞报告**仅**通过下方 GitHub Private Security Advisory 受理（不设独立邮件/PGP 渠道，避免不可投递地址）。

## 🧭 At a glance

- **Zero-Key** — no private keys, seed phrases, or signing secrets.
- **Zero-Telemetry** — no analytics, beacons, or behavioral telemetry.
- **Zero-Trust** — untrusted input must be validated, simulated, and rejected by default.
- **Private disclosure only** — public issues are not the place for active vulnerabilities.

## The Triple-Zero Standard 🛡️

Security is not a feature; it is the operating boundary.

Lirix is built around the Triple-Zero Standard:

- 🛑 **Zero-Key** — Lirix never requests, stores, derives, encrypts, or transmits private keys, seed phrases, or signing secrets.
- 👁️‍🗨️ **Zero-Telemetry** — Lirix does not ship analytics, tracking beacons, or behavioral telemetry out of the trust boundary.
- 🛡️ **Zero-Trust** — Every untrusted input must be validated, simulated, and rejected by default if confidence is insufficient.

These three principles are not slogans. They define the core security contract of the project.

## Scope

### In scope

The following are considered security-relevant and should be reported:

- Private key or secret exposure
- Unsafe fallback behavior during RPC, API, or simulation failure
- Authorization bypasses or validation bypasses
- Integrity issues that could affect transaction safety
- Unsafe decoding, proxy traversal, or ABI parsing behavior
- Unintended telemetry or data egress
- Any condition that breaks the fail-closed guarantee inside the Lirix core boundary
- Subversion, bypass, or deterministic manipulation of the L4 Dynamic BFT Quorum, including any attempt to defeat the `math.ceil(N * 2/3)` quorum threshold
- Subversion, bypass, injection, or schema-poisoning of the L5 `ShadowPolicySchema`
- Path traversal, environment corruption, or trust-boundary escape via the `lirix init` CLI

### Out of scope

The following are not security vulnerabilities in Lirix itself:

- The raw quality, creativity, or correctness of an LLM’s generated text
- Agent prompt quality or prompt engineering style
- User mistakes outside the Lirix validation boundary
- Network outages or failures in third-party providers beyond the project’s control
- Issues that require private infrastructure access that the reporter does not legitimately possess

If a problem depends on the model’s language quality rather than the Lirix boundary, it is a product or workflow issue, not a security defect.

## Vulnerability Reporting

**Do NOT open public issues for zero-days or active vulnerabilities.**

Use the private disclosure path below instead.

### Reporting contact

**Submit vulnerabilities only through GitHub Private Security Advisories** (do not open public issues for undisclosed security defects):

`https://github.com/lokii-D/lirix/security/advisories/new`

Use the advisory title and description fields to summarize impact; include the subject line `Lirix Security Report` in the title or first line when possible.

### What to include

Please provide as much detail as possible:

- Affected version or commit hash
- Environment and dependency details
- Clear steps to reproduce
- Expected behavior and observed behavior
- Logs, traces, screenshots, or sample payloads when available
- Any mitigation ideas or preliminary analysis

### Response expectations

- Acknowledgement of receipt within 48 hours
- Initial severity assessment within 7 business days
- A coordinated remediation and disclosure plan for confirmed issues

## Responsible Disclosure and Safe Harbor

We support good-faith security research conducted responsibly and in compliance with applicable law.

Researchers must not:

- Exfiltrate secrets
- Exploit a vulnerability beyond the minimum steps required to demonstrate impact
- Disrupt service for other users
- Publish proof-of-concepts before a coordinated disclosure plan is agreed

If you are unsure whether your finding is in scope, report it privately and let the maintainers assess it.

## Security Principles

Lirix must fail closed.

If a request cannot be verified with high confidence, it must not execute. If the boundary cannot be trusted, the safe outcome is rejection.

---

## 中文（完整对照）

### 🧭 一眼看懂

- **Zero-Key**：不索取、不保存、不推导、不加密传输私钥、助记词或签名材料。
- **Zero-Telemetry**：默认不把分析探针、行为埋点或跟踪信标送出信任域。
- **Zero-Trust**：凡不可信输入，必须经过校验与模拟；信心不足则默认拒绝。
- **私下披露**：活跃漏洞只走 GitHub Private Security Advisories，不走公开 Issue。

### 三重零边界 🛡️

安全不是功能列表里的一行，而是**运行边界**。

- 🛑 **Zero-Key（零密钥）**：Lirix 不索取、不保存、不推导、不加密传输私钥、助记词或签名材料。
- 👁️‍🗨️ **Zero-Telemetry（零遥测）**：默认不把分析探针、行为埋点或跟踪信标送出信任域。
- 🛡️ **Zero-Trust（零信任）**：凡不可信输入，必须经过校验与模拟；信心不足则**默认拒绝**。

### 收录范围

**属于安全议题：**

- 私钥或秘密泄露
- RPC / API / 模拟失败下的不安全回退
- 授权或校验绕过
- 影响交易完整性的缺陷
- 不安全的解码、代理穿透或 ABI 解析
- 意外遥测或数据外泄
- 破坏 Lirix 核心边界内 **fail-closed** 保证的情形
- 针对 **L4** 动态仲裁阈值的确定性操纵
- 对 **L5** `ShadowPolicySchema` 的注入或模式投毒
- 借助 **`lirix init` CLI** 的路径穿越、环境污染或信任域逃逸

**不属于 Lirix 自身漏洞：**

- 纯 LLM 文本质量
- 提示词工程水平
- 用户在验证边界之外的误操作
- 超出项目控制的三方网络故障
- 需要不当私有基础设施访问才能触发的情形

### 报告流程

**勿**为活跃 0-day 或可利用漏洞开公开 Issue。请**仅**通过 GitHub 私密安全公告提交：

`https://github.com/lokii-D/lirix/security/advisories/new`

建议在标题或正文首行包含 `Lirix Security Report` 以便维护者筛选。

### 响应期望

与英文 **Response expectations** 一致：收悉确认（48 小时内）、初步分级（7 个工作日内）、对已确认问题协调修复与披露节奏。

### 安全原则（中文）

Lirix 必须 **fail-closed**：无法高置信验证的请求，不得继续执行；边界不可信时，**安全出口是拒绝**。
