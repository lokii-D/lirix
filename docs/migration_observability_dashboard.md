# Migration Observability Dashboard


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This document tracks migration progress for architecture convergence milestones.

## ⚡ How to Refresh

Run:

`python tools/migration_observability_report.py`

The script updates `audit_artifacts/migration_observability/latest.json` and
`audit_artifacts/migration_observability/latest.md`.

## 📡 Milestone Signals

- **M1 API Surface**
  - Canonical root export set is stable.
  - Compatibility import warnings are observable.
  - Docs/examples only use canonical imports.
- **M2 Config Authority**
  - Runtime fallback logic exists only in `config_authority`.
  - Resolved config carries source tags and stable provenance.
- **M3 CI Lane Split**
  - Full coverage suite executes once in required lane.
  - Fast lane excludes slow/e2e/network/perf workloads.
- **M4 Test Topology**
  - Fragmented micro-file count trends downward by themed aggregation.
  - Coverage remains at fail-under 100.

## 📂 Current Snapshot

See generated report:

- `audit_artifacts/migration_observability/latest.md`
- `audit_artifacts/migration_observability/latest.json`
