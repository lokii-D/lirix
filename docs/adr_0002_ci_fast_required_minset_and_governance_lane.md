**EN:** Architecture Decision Record (ADR); repository Markdown conventions: [`documentation_styleguide.md`](documentation_styleguide.md).  
**中文：** 架构决策记录；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## ADR 0002: CI fast_required minimal set and governance lane split

### Status

Accepted (Round4).

---

### Context

`Fast Required` is intended to be the **minimal deterministic** pull-request gate: it should be
fast, reproducible in a clean checkout, and have clear failure attribution. Over time, multiple
“governance/process” gates accumulated inside `Fast Required`, causing PR CI to become noisy and
hard to reason about (and overly coupled to evolving governance artifacts).

At the same time, we still need those governance gates to run somewhere and to remain regression
safe.

---

### Decision

We split gates into two categories:

- **Quality / Build required (PR-blocking)**: stays in `Fast Required`.
- **Governance / Process (non-PR-blocking)**: moves to a separate workflow lane, run on `push/main`,
  `schedule`, and `workflow_dispatch` (and optionally on PR as non-required).

#### PR-blocking (Fast Required) criteria

A gate can stay in `Fast Required` if it satisfies all:

- **Deterministic inputs**: reads only repository files and/or deterministic local computation.
- **Actionable output**: failures point to a specific file/path with a clear remediation.
- **Short runtime**: expected to run in seconds (not minutes).
- **Contracted**: has at least one `tests/test_tools/*` test verifying it can run in a clean checkout.

---

#### Governance-lane criteria (migrated out)

A gate must be migrated out of `Fast Required` when any is true:

- **Process coupling**: evaluates evolving governance registries/checklists whose updates are
  not required for every PR.
- **Organizational dependency**: requires org-level configuration or live GitHub API access to be
  meaningful; must fail-closed only when a token is available and drift is real.
- **Slow/expensive**: runtime is high or failure modes are non-local.

---

### Consequences

- PR required checks are kept minimal and stable.
- Governance gates still run continuously, but do not block contributor PRs by default.
- Documentation and drift gates must reflect the split:
  `docs/branch_protection_required_checks.md`, `tools/required_check_policy_gate.py`,
  `tools/branch_protection_drift_gate.py`, and `tools/ci_lane_responsibility_gate.py`.

---

### Gate classification (Round4)

**Remain in Fast Required**

- `tools/hygiene_gate.py`
- `ruff`, `black --check`, `mypy --strict`
- explicit governance pytest subset (contracted tests list)
- `tools/registry_authority_contract_gate.py`
- `tools/contract_manifest_gate.py`
- `tools/required_check_policy_gate.py`
- `tools/audit_internal_link_gate.py`
- `tools/root_import_surface_gate.py`
- `tools/test_monkeypatch_convention_gate.py --strict`
- `tools/test_topology_admission_gate.py`
- `tools/migration_observability_report.py`
- `tools/no_internal_imports_gate.py` (added Round4)

**Move to Governance lane**

- `tools/branch_protection_drift_gate.py`
- `tools/ci_lane_responsibility_gate.py`
- `tools/failure_surface_triage_gate.py`
- `tools/legacy_sunset_gate.py`
- `tools/phase_exit_checklists_gate.py`

