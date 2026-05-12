---
title: Policy lifecycle and rollback
purpose: deterministic selection + rollback semantics for audit
compatibility: additive-only documentation; no runtime behavior changes
---

**EN:** Policy bundle selection and rollback semantics (audit companion); conventions: [`documentation_styleguide.md`](documentation_styleguide.md).  
**中文：** 策略包选择与回滚语义（审计配套）；体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## Scope

This document specifies the **selection and rollback semantics** for `ShadowAuditor` policy bundles.
It is an audit companion to:

- `lirix/layers/l5_shadow_auditor.py`
- `tests/test_layers/test_shadow_auditor_policy_bundle.py`

## Inputs (caller-provided)

When `security_policy` is a mapping, `ShadowAuditor` may read:

- **`policy_bundle`**: a `PolicyBundle` payload (validated by Pydantic)
- **`policy_environment`**: desired environment (default `"default"`)
- **`policy_version`**: preferred version override (optional)
- **`policy_lifecycle_mode`**: `"digest_verified"` (default); `"legacy"` and `"signed_only"` are
  migration aliases that are coerced to `"digest_verified"` during config normalization
- **`PolicyVersion.integrity_digest`**: preferred SHA-256 hex of the canonical policy JSON; `signature` is
  a deprecated field name for the same integrity value (not a cryptographic signature)

## Selection algorithm (deterministic)

Given a validated `PolicyBundle` with a list of versions, selection is:

1. **Preferred version**: if `policy_version` is provided, select the first version where:\n
   - `version == policy_version` and `environment == policy_environment`
2. **Active version**: else if `bundle.active_version` exists, select the first version where:\n
   - `version == bundle.active_version` and `environment == policy_environment`
3. **Environment-first fallback**: else select the first version where:\n
   - `environment == policy_environment`
4. **Global fallback**: else select `versions[0]`
5. **Empty bundle**: if `versions` is empty, fall back to the internal default policy.

If the requested environment is not found and a fallback is used, the decision report includes a
conflict entry:

- `bundle.conflicts[].key == "environment"`
- `bundle.conflicts[].reason == "requested_environment_not_found_fallback_used"`

## Rollback semantics

After selection, if the selected version has:

- `status != "active"` **and**
- `rollback_to` is a non-empty string

…then `ShadowAuditor` attempts rollback:

- Find a rollback candidate where:\n
  - `version == rollback_to` and `environment == selected.environment`
- If found:\n
  - select the rollback candidate\n
  - set `bundle.rollback_applied = True`\n
  - add a conflict entry:\n
    - `key="policy_version"` and `reason="rollback_applied"`
- If not found:\n
  - keep the original selection\n
  - keep `bundle.rollback_applied = False`

## Digest-verified mode (`policy_lifecycle_mode == "digest_verified"`)

In digest-verified mode (including the deprecated alias `signed_only`), the selected policy must satisfy:

- `status == "active"`
- `integrity_digest` or `signature` is set and equals the SHA-256 of the canonical JSON policy payload

This is **integrity-only** (self-consistency of the policy blob). A future release may add optional
asymmetric signature verification with pinned public keys under an explicit mode name.

If either constraint fails, `ShadowAuditor` raises `LirixPolicyViolationException` (fail-closed).

## Convergence policy (single-stack)

Single-stack target is `policy_lifecycle_mode=digest_verified`.

- Strict mode requires digest-verified behavior.
- Legacy lifecycle runtime branch is retired; only digest-verified executes at runtime.
- Alias inputs are migration-only and produce deprecation warnings.
- Next major release removes alias inputs entirely.

Migration state machine:

- **Removed**: runtime `policy_lifecycle_mode=legacy`; runtime `rpc_evidence_mode=legacy|v2_dual`.
- **Migrating**: input aliases (`legacy`, `signed_only`, `v2_dual`) are coercion-only compatibility shims.
- **Pending removal**: alias-input acceptance is scheduled for removal in the next major release.

## Evidence surfaces (audit keys)

Policy decision reports emitted by Lirix include the following auditable fields:

- `policy_decision.lifecycle_mode`
- `policy_decision.bundle.source`
- `policy_decision.bundle.rollback_applied`
- `policy_decision.bundle.conflicts[]`

See: `tests/test_layers/test_shadow_auditor_policy_bundle.py` for executable proof.

