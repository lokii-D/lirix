**EN:** Baseline snapshot policy for CI gates; Markdown conventions: [`documentation_styleguide.md`](../documentation_styleguide.md).  
**中文：** CI 门禁所用基线快照说明；体例见 [`documentation_styleguide.md`](../documentation_styleguide.md)。

## Baselines

Baselines are **frozen, reviewable** snapshots used by CI gates to implement “no regression”
policies without relying on mutable local artifacts or ephemeral CI state.

### `migration_observability_baseline.json`

Used as the authoritative baseline for:

- `tools/test_topology_admission_gate.py` (micro-ratio regression)
- `tools/migration_observability_report.py` (trend anchoring / integrity policy)

#### Update process (main baseline bump)

- Run the snapshot generator:

```bash
.venv/bin/python tools/migration_observability_report.py
```

- Review `audit_artifacts/migration_observability/latest.json` and confirm the changes are intended.
- Update `docs/baselines/migration_observability_baseline.json` to match the **stable subset**
  (counts + policies, not file lists) and commit the change as part of the same PR that justifies it.

#### Contract

- The baseline file must remain **small and stable**: counts and policies only.
- Any baseline bump must be explicitly justified in PR description / release notes.

