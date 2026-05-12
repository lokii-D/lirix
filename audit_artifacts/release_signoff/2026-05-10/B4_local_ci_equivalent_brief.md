## Local CI-equivalent replay (2026-05-10)

This brief summarizes the local pre-release CI-equivalent replay, executed in an isolated virtualenv
(`.venv_ci312`) using **Python 3.12.x**, aligned with `.github/workflows/ci.yml`.

### Environment

- Python: see `B4_env_python_version.log`
- Virtualenv: `.venv_ci312` (workspace-local; no system changes)

### Steps executed (CI semantics)

- Ruff: `B4_ruff_ci312.log`
- Black (check): `B4_black_check_ci312.log`
- MyPy (strict, `lirix`): `B4_mypy_strict_lirix_ci312.log`
- Governance gate (explicit test list from CI): `B4_governance_gate_explicit_pytest_ci312.log`
- Release notes gate (string presence checks, CI-equivalent without `rg`):
  - `B4_release_notes_gate_1_ci312.log`
  - `B4_release_notes_gate_2_ci312.log`
- Docs contract gate: `B4_docs_contract_gate_contract_manifest_ci312.log`
- Internal doc link gate: `B4_audit_internal_link_gate_ci312.log`
- Root import surface gate: `B4_root_import_surface_gate_ci312.log`
- Monkeypatch convention gate (strict): `B4_monkeypatch_convention_gate_strict_ci312.log`
- Full pytest + coverage (CI flags): `B4_pytest_full_cov_ci312.log`

### Result

- All steps above completed with exit code **0**.

Cross-link (post-bundle maintenance): [`docs/documentation_styleguide.md`](../../../docs/documentation_styleguide.md).
