## DeprecationWarning baseline (migration-only) — 2026-05-10

### Policy

During the migration window, the only allowed `DeprecationWarning` instances are those emitted by
**coercion-only migration aliases** during config normalization:

- `policy_lifecycle_mode=legacy` → coerced to `digest_verified`
- `rpc_evidence_mode=legacy` → coerced to `v2_only`
- `policy_lifecycle_mode=signed_only` → coerced to `digest_verified` (deprecated label)

Any *new* `DeprecationWarning` outside these migration aliases is considered a release-blocking regression.

### Baseline evidence (logs)

The following logs contain the baseline warning set observed in this sign-off:

- Full pytest (warnings enabled): `C4_full_pytest_warnings_baseline_ci312.log`
- Governance gate parity run: `C3_governance_gate_parity_ci312.log`
- Fast regression batch: `C2_fast_regression_batch_ci312.log`

### Expected counts (migration alias warnings)

Observed repeatedly in the suite:

- `DeprecationWarning: policy_lifecycle_mode=legacy is retired; coercing to digest_verified.` (2 occurrences)
- `DeprecationWarning: rpc_evidence_mode=legacy is retired; coercing to v2_only.` (2 occurrences)
- `DeprecationWarning: policy_lifecycle_mode=signed_only is deprecated; use digest_verified.` (1 occurrence)

Total expected migration-alias `DeprecationWarning` count: **5**.

### Non-migration warning note (tooling)

`C4_full_pytest_warnings_baseline_ci312.log` also includes a `PytestDeprecationWarning` from `pytest-asyncio`
about an unset loop-scope config option. This is not a Lirix runtime migration warning; it is tooling-level and
should be tracked separately from the migration-only deprecation policy.

### Non-migration note (stdlib / asyncio, Python 3.14+)

On Python 3.14+, the standard library emits `DeprecationWarning` for `asyncio.get_event_loop_policy` (scheduled
removal in 3.16). The test suite runs with `filterwarnings = ["error"]`; a **narrow** `ignore:.*get_event_loop_policy.*`
entry in `pyproject.toml` prevents unrelated stdlib churn from failing CI while keeping migration-alias warnings
strict.

Cross-link (post-bundle maintenance): [`docs/documentation_styleguide.md`](../../../docs/documentation_styleguide.md).
