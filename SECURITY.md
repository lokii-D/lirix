# Security Policy for Lirix

## The Triple-Zero Standard

Security is not a feature; it is the operating boundary.

Lirix is built around the Triple-Zero Standard:

- **Zero-Key** — Lirix never requests, stores, derives, encrypts, or transmits private keys, seed phrases, or signing secrets.
- **Zero-Telemetry** — Lirix does not ship analytics, tracking beacons, or behavioral telemetry out of the trust boundary.
- **Zero-Trust** — Every untrusted input must be validated, simulated, and rejected by default if confidence is insufficient.

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

- Email: `security@lirix.invalid` *(placeholder)*
- PGP key: `https://example.com/lirix-security-pgp.asc` *(placeholder)*
- Optional GitHub private advisory: `https://github.com/lokii-D/lirix/security/advisories/new`

If you are using PGP, encrypt your report to the published security key before sending it. Include the subject line `Lirix Security Report`.

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
