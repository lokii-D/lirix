# Failure Surface Triage Framework


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

This framework classifies failure surfaces into:

- `historical`: existing known failure before current change set
- `regression`: newly introduced by current change set
- `environment`: external/infra flake (network, CI capacity, toolchain drift)

## 57-failed Tracking Contract

The machine-readable file `docs/failure_surface_triage_57.json` is the canonical checklist.

Required fields per case:

- `id`
- `category`
- `owner`
- `status`
- `evidence`

Allowed `category`: `historical`, `regression`, `environment`.
Allowed `status`: `open`, `triaged`, `fixed`, `wont_fix`.

## Failure Case Anchors

Canonical anchors for machine-readable evidence pointers:

- <a id="fs-001"></a>FS-001
- <a id="fs-002"></a>FS-002
- <a id="fs-003"></a>FS-003
- <a id="fs-004"></a>FS-004
- <a id="fs-005"></a>FS-005
- <a id="fs-006"></a>FS-006
- <a id="fs-007"></a>FS-007
- <a id="fs-008"></a>FS-008
- <a id="fs-009"></a>FS-009
- <a id="fs-010"></a>FS-010
- <a id="fs-011"></a>FS-011
- <a id="fs-012"></a>FS-012
- <a id="fs-013"></a>FS-013
- <a id="fs-014"></a>FS-014
- <a id="fs-015"></a>FS-015
- <a id="fs-016"></a>FS-016
- <a id="fs-017"></a>FS-017
- <a id="fs-018"></a>FS-018
- <a id="fs-019"></a>FS-019
- <a id="fs-020"></a>FS-020
- <a id="fs-021"></a>FS-021
- <a id="fs-022"></a>FS-022
- <a id="fs-023"></a>FS-023
- <a id="fs-024"></a>FS-024
- <a id="fs-025"></a>FS-025
- <a id="fs-026"></a>FS-026
- <a id="fs-027"></a>FS-027
- <a id="fs-028"></a>FS-028
- <a id="fs-029"></a>FS-029
- <a id="fs-030"></a>FS-030
- <a id="fs-031"></a>FS-031
- <a id="fs-032"></a>FS-032
- <a id="fs-033"></a>FS-033
- <a id="fs-034"></a>FS-034
- <a id="fs-035"></a>FS-035
- <a id="fs-036"></a>FS-036
- <a id="fs-037"></a>FS-037
- <a id="fs-038"></a>FS-038
- <a id="fs-039"></a>FS-039
- <a id="fs-040"></a>FS-040
- <a id="fs-041"></a>FS-041
- <a id="fs-042"></a>FS-042
- <a id="fs-043"></a>FS-043
- <a id="fs-044"></a>FS-044
- <a id="fs-045"></a>FS-045
- <a id="fs-046"></a>FS-046
- <a id="fs-047"></a>FS-047
- <a id="fs-048"></a>FS-048
- <a id="fs-049"></a>FS-049
- <a id="fs-050"></a>FS-050
- <a id="fs-051"></a>FS-051
- <a id="fs-052"></a>FS-052
- <a id="fs-053"></a>FS-053
- <a id="fs-054"></a>FS-054
- <a id="fs-055"></a>FS-055
- <a id="fs-056"></a>FS-056
- <a id="fs-057"></a>FS-057
