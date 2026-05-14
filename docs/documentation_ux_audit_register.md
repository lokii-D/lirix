---
title: Documentation UX audit register
purpose: close G-008 with a dated, audience-scoped read-through record (no substitute for code review)
---

# Documentation UX audit register

**Audit date:** 2026-05-14
**Scope:** `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/` index pages cited from those entry points (`ci_gate_matrix.md`, `tools_gates_index.md`, `contributing_local_tests.md`, `migration_legacy_to_v2.md`, `release_notes.md`, `release_pr_checklist.md`, `preflight_remediation_executor_handoff.md`).

## Audience map (“who reads what”)

| Surface | Primary reader | Job-to-be-done |
| --- | --- | --- |
| `README.md` | Integrators / evaluators | Install, mental model, links into SSOT docs |
| `CONTRIBUTING.md` | Contributors / reviewers | Python 3.12 parity, harness gates, Black pin, skip charter |
| `SECURITY.md` | Reporters / auditors | Triple-Zero, scope, private advisory path |
| `docs/ci_gate_matrix.md` | CI / release engineers | Workflow ↔ gate truth |
| `docs/contributing_local_tests.md` | Contributors | addopts pitfalls, **Black 24.10.0** vs global Black |
| `docs/migration_legacy_to_v2.md` + `docs/release_notes.md` | Upgraders | Deprecation / next-major policy |

## Consistency checks performed

- **Stable vs migration:** `README.md` § Stability states Production/Stable for 2.x **and** explains that `DeprecationWarning` / alias coercion are bounded migration shims — aligned with `docs/release_notes.md` Unreleased and `docs/migration_legacy_to_v2.md` (no “silent GA” contradiction).
- **Toolchain truth:** `CONTRIBUTING.md` and `docs/contributing_local_tests.md` both state **Black 24.10.0** via `pip install -e ".[dev]"` and warn against global Black major drift (**R-ENV-001**).
- **Security ↔ contrib:** Triple-Zero and fail-closed language in `SECURITY.md` matches the non-negotiables list in `CONTRIBUTING.md` (no conflicting promises).
- **Preflight R-002:** Human playbook (`docs/preflight_remediation_executor_handoff.md`) and `tools/preflight_remediation_contract.json` list the same hazard path as `tools/validators.py` (`test_session_agent_timeline_order_happy_path.py`).

## Residual / explicit non-claims

- This register is a **structured spot read**, not a line-by-line editorial pass of every file under `docs/**`.
- Historical logs under `audit_artifacts/release_signoff/**` are **immutable evidence** and may mention retired filenames; do not “rewrite history” there.

## Sign-off for G-008

G-008 (documentation UX / duty boundaries) is **closed for this audit cycle** at the scope above; expand scope only when navigation or policy materially changes.
