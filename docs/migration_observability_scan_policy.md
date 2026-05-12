**EN:** Source-only vs artifact metrics policy for migration observability scans; conventions: [`documentation_styleguide.md`](documentation_styleguide.md).  
**中文：** 迁移可观测性扫描的 source-only 策略；体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## 🔍 Migration observability scan policy (source-only)

The migration observability snapshot (`tools/migration_observability_report.py`) produces both:

- **source_only** metrics: intended to be stable and anchored to repository sources
- **artifact_noise** metrics: captures drift from local/CI build artifacts (not policy relevant)

### Excluded path parts

The **source-only** scan MUST exclude any paths that contain:

- `.git`
- `.tox`
- `build`
- `dist`
- `site-packages`
- `.venv*` (any directory component that starts with `.venv`)

This policy is contracted by tests and must not be weakened without an explicit ADR update.

