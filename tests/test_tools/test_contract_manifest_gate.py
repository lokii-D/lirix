from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def _load_gate_module():
    from tools import contract_manifest_gate

    return contract_manifest_gate


def test_exception_lattice_allows_alias_and_multi_inheritance() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._assert_exception_inheritance_contract(
        api_doc=(
            "仅安全相关子集继承自 `LirixSecurityException`\n"
            "only the security-oriented subset uses"
        ),
        exceptions_source=(
            "class LirixBaseException(Exception):\n"
            "    pass\n"
            "BaseAlias = LirixBaseException\n"
            "class Mixin(Exception):\n"
            "    pass\n"
            "class LirixSecurityException(BaseAlias, Mixin):\n"
            "    pass\n"
            "class LirixPolicyViolationException(LirixSecurityException):\n"
            "    pass\n"
            "class NonSecurityError(BaseAlias):\n"
            "    pass\n"
        ),
        failures=failures,
    )
    assert failures == []


def test_validate_and_simulate_contract_enforces_dataflow_origin() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._assert_validate_and_simulate_return_contract(
        client_source=(
            "def validate_and_simulate():\n"
            "    out = {'to': '0x1'}\n"
            "    trace = object()\n"
            "    simulation_outcome = dict(out)\n"
            "    auditor = object()\n"
            "    policy_decision = dict(auditor.decision_report())\n"
            "    t = trace.to_dict()\n"
            "    return {\n"
            "        'validated': True,\n"
            "        'simulation_outcome': simulation_outcome,\n"
            "        'policy_decision': policy_decision,\n"
            "        'agent_feedback': _build_agent_feedback_success(),\n"
            "        'validation_session': {},\n"
            "        'replay_bundle': {},\n"
            "        'forensic_bundle': {},\n"
            "        'security_trace': t,\n"
            "        'evidence_v2': {},\n"
            "        'migration_modes': {},\n"
            "    }\n"
        ),
        failures=failures,
    )
    assert failures == []


def test_validate_and_simulate_contract_accepts_build_result_envelope() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._assert_validate_and_simulate_return_contract(
        client_source=(
            "def validate_and_simulate():\n"
            "    out = {'simulation_ok': True}\n"
            "    trace = object()\n"
            "    auditor = object()\n"
            "    simulation_outcome = dict(out)\n"
            "    policy_decision = dict(auditor.decision_report())\n"
            "    t = trace.to_dict()\n"
            "    return self._build_result(\n"
            "        status='approved',\n"
            "        decision='approved',\n"
            "        payload=result_envelope_builder(\n"
            "            payload=self._simulation_payload(out, validated=True),\n"
            "        ),\n"
            "        agent_feedback=_build_agent_feedback_success(),\n"
            "        validation_session={},\n"
            "        replay_bundle={},\n"
            "        forensic_bundle={},\n"
            "        security_trace=t,\n"
            "        evidence_schema_version='1',\n"
            "        evidence_v2={},\n"
            "    )\n"
        ),
        failures=failures,
    )
    assert failures == []


def test_readme_contract_accepts_whitelisted_broadcast_pattern() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._assert_readme_broadcast_contract(
        readme=(
            "```python\n"
            "result = guardian.validate_and_simulate('swap', raw)\n"
            "tx_payload = {\n"
            "    'to': result['to'],\n"
            "    'data': result['data'],\n"
            "    'value': result.get('value', 0),\n"
            "}\n"
            "sign_and_broadcast(tx_payload)\n"
            "```\n"
        ),
        failures=failures,
    )
    assert failures == []


def test_readme_contract_rejects_raw_result_broadcast() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._assert_readme_broadcast_contract(
        readme=(
            "```python\n"
            "result = guardian.validate_and_simulate('swap', raw)\n"
            "sign_and_broadcast(result)\n"
            "```\n"
        ),
        failures=failures,
    )
    assert failures


def test_governance_explicit_gate_tests_ssot_covers_anchors() -> None:
    gate = _load_gate_module()
    extracted = gate._governance_explicit_gate_tests_ssot()
    assert len(extracted) >= gate._GOVERNANCE_GATE_EXPLICIT_MIN_TESTS
    for t in gate._GOVERNANCE_GATE_CI_YML_ANCHORS:
        assert t in extracted


def test_assert_governance_step_invokes_test_harness_accepts_repo_ci_yml() -> None:
    gate = _load_gate_module()
    root = Path(__file__).resolve().parents[2]
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    failures: list[str] = []
    gate._assert_governance_step_invokes_test_harness(ci, failures)
    assert failures == []


def test_assert_governance_step_invokes_test_harness_rejects_non_harness_run() -> None:
    gate = _load_gate_module()
    step = gate.GOVERNANCE_GATE_EXPLICIT_STEP_NAME
    ci = f"""
      - name: {step}
        run: |
          python -m pytest -q tests/test_core/test_canonical_semantics.py
"""
    failures: list[str] = []
    gate._assert_governance_step_invokes_test_harness(ci, failures)
    assert failures


def test_validate_governance_explicit_list_short_list_floor_failure_substrings() -> None:
    gate = _load_gate_module()
    extracted = [f"tests/test_core/test_short_{i}.py" for i in range(7)]
    failures: list[str] = []
    gate._validate_governance_explicit_list(extracted, failures)
    joined = "\n".join(failures)
    assert "explicit gate list too short" in joined
    assert f"{len(extracted)} < {gate._GOVERNANCE_GATE_EXPLICIT_MIN_TESTS}" in joined
    assert "validators.py" in joined


def test_validate_governance_explicit_list_empty_extraction_message() -> None:
    gate = _load_gate_module()
    failures: list[str] = []
    gate._validate_governance_explicit_list([], failures)
    assert failures == [
        "ci-governance-gate: failed to load explicit gate test list from "
        "`tools/validators.py` (`GOVERNANCE_EXPLICIT_PYTEST_PATHS`)"
    ]


def test_validate_governance_explicit_list_missing_anchor_paths() -> None:
    gate = _load_gate_module()
    extracted = [f"tests/test_core/test_dummy_gate_{i}.py" for i in range(8)]
    failures: list[str] = []
    gate._validate_governance_explicit_list(extracted, failures)
    assert any("missing gated test" in msg for msg in failures)
    for anchor in gate._GOVERNANCE_GATE_CI_YML_ANCHORS:
        assert any(anchor in msg for msg in failures)


def test_assert_governance_explicit_step_line_accepts_repo_ci_yml() -> None:
    gate = _load_gate_module()
    root = Path(__file__).resolve().parents[2]
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    failures: list[str] = []
    gate._assert_governance_explicit_step_line_in_ci_yml(ci, failures)
    assert failures == []


def test_assert_governance_explicit_step_line_rejects_wrong_step_title() -> None:
    gate = _load_gate_module()
    bad = """
jobs:
  fast_required:
    steps:
      - name: Governance gate
        run: |
          pytest tests/x.py
"""
    failures: list[str] = []
    gate._assert_governance_explicit_step_line_in_ci_yml(bad, failures)
    assert failures and "Docs contract gate" in failures[0]


def test_tools_gates_index_row_parity_matches_disk() -> None:
    gate = _load_gate_module()
    root = Path(__file__).resolve().parents[2]
    index_md = (root / "docs/tools_gates_index.md").read_text(encoding="utf-8")
    failures: list[str] = []
    gate._validate_tools_gates_index_row_parity(index_md, failures)
    assert failures == []


def test_tools_gates_index_row_parity_fails_when_main_row_lacks_backtick_pipe_shape() -> None:
    """Regression: only ``| `<subcommand>` |`` rows count; a hand-edited table must not silently under-count."""
    gate = _load_gate_module()
    index_md = """# Tools gates (fixture)

| Subcommand | Notes |
| --- | --- |
| `hygiene` | OK — counted by `_TOOLS_GATES_INDEX_MAIN_ROW_RE` |
| contract-manifest | BAD — missing backticks; not counted as a main-table gate row |

## Related tools

| Other | Notes |
| --- | --- |
| helper.py | excluded from parity scan |
"""
    failures: list[str] = []
    with patch.object(gate, "_count_harness_gate_modules", return_value=2):
        gate._validate_tools_gates_index_row_parity(index_md, failures)
    assert failures
    assert "tools-gates-index-parity" in failures[0]
