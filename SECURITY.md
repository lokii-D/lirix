## The Zero-Trust Manifesto | 零信任安全宣言

Security is not a feature; it is physical isolation. Lirix is engineered under a strict Zero-Trust philosophy to protect your on-chain sovereignty.
- **Zero-Key Architecture**: Lirix operates strictly as a pre-execution firewall. It NEVER requests, calculates, encrypts, or stores private keys or mnemonics.
- **Fail-Closed Principle**: In the event of RPC divergence, API timeouts, or unhandled states, Lirix will silently block the execution. We never fallback to stale data.
- **Zero-Telemetry**: Lirix runs entirely within your VPC. Zero tracking, zero outbound analytical pings.

安全不是一个功能，而是物理隔离。Lirix 秉持严格的零信任哲学，以捍卫您的链上主权。
- **零密钥架构**：Lirix 纯粹作为前置执行防火墙运行。绝不请求、计算、加密或存储任何私钥或助记词。
- **静默阻断原则**：面对 RPC 分叉、API 超时或未知状态，Lirix 将直接阻断执行，绝不使用过期陈旧数据进行危险降级。
- **零埋点追踪**：Lirix 完全在您的私有网络（VPC）内运行。零数据上报，零外部探针。

### Reporting a Vulnerability | 漏洞报告通道
Please DO NOT report security vulnerabilities through public GitHub issues. Reach out directly via [Insert Security Email / GitHub Security Advisories link].
请绝对不要在公开的 GitHub Issue 中报告安全漏洞。请直接通过 [预留安全邮箱 / GitHub Security Advisories] 与我们联系。

### PGP Key
XXXX XXXX XXXX XXXX
For high-severity vulnerabilities involving potential fund loss, we strongly recommend encrypting your vulnerability report with this PGP public key.

### Response SLA
The security team will acknowledge receipt of a vulnerability within 48 hours and provide an initial severity assessment and remediation timeline within 7 business days.

## Security Policy

Lirix is designed to fail closed. If a request cannot be verified with high confidence, it must not execute.

### What we consider a security issue
- Exposure of private keys, mnemonics, or other secrets
- Unsafe fallback behavior during RPC or API failures
- Authorization or validation bypasses
- Integrity issues that could affect transaction safety
- Sensitive data leakage or unintended telemetry

### What to include in a report
Please provide as much detail as possible, including:
- Affected version or commit hash
- Environment details
- Steps to reproduce
- Expected and actual behavior
- Any logs, traces, or screenshots that help us validate the issue

### Our response process
We will acknowledge receipt of a valid report and investigate promptly. If confirmed, we will coordinate remediation and disclosure in a responsible manner.

### Safe harbor
We support good-faith security research that follows responsible disclosure principles and does not violate applicable laws or disrupt service for others.
