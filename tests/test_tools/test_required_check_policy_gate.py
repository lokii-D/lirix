from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _load_policy_module():
    from tools import ci_gate_shared

    return ci_gate_shared


def _minimal_ci_yml_fragment() -> str:
    return """
on:
  pull_request:
    branches: [main]
jobs:
  fast_required:
    name: Fast Required
  pr_compat_smoke:
    if: github.event_name == 'pull_request'
    name: PR Compatibility Smoke (ubuntu-latest, py3.12)
  coverage_required:
    if: github.event_name != 'pull_request'
    name: Coverage Required (Single Authority)
  compatibility_matrix:
    if: github.event_name != 'pull_request'
    name: Compatibility Matrix (ubuntu-latest, py3.12)
    strategy:
      matrix:
        python-version: ["3.9", "3.14"]
"""


def _minimal_governance_lane_fragment() -> str:
    return """
jobs:
  governance_gates:
    name: Governance Gates
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
"""


def _minimal_policy_doc_fragment(*, mention_governance_gates: bool = True) -> str:
    tail = "Non-PR lane: see Governance Gates job vs steps." if mention_governance_gates else "Non-PR lane: see Other Gates job vs steps."
    return f"""
## Required on Pull Requests

- `Fast Required`
- `PR Compatibility Smoke (Linux, py3.12)`

{tail}
"""


def test_evaluate_required_check_policy_minimal_fragments_pass() -> None:
    mod = _load_policy_module()
    failures: list[str] = []
    mod.evaluate_required_check_policy(
        _minimal_ci_yml_fragment(),
        _minimal_governance_lane_fragment(),
        _minimal_policy_doc_fragment(),
        failures,
    )
    assert failures == []


def test_evaluate_required_check_policy_fails_when_governance_lane_job_renamed() -> None:
    mod = _load_policy_module()
    bad_lane = """
jobs:
  governance_gates:
    name: Governance Lane (wrong title)
    runs-on: ubuntu-latest
"""
    failures: list[str] = []
    mod.evaluate_required_check_policy(
        _minimal_ci_yml_fragment(),
        bad_lane,
        _minimal_policy_doc_fragment(),
        failures,
    )
    assert any("Governance Gates` job name missing" in m for m in failures)


def test_evaluate_required_check_policy_fails_when_policy_omits_governance_gates_prose() -> None:
    mod = _load_policy_module()
    failures: list[str] = []
    mod.evaluate_required_check_policy(
        _minimal_ci_yml_fragment(),
        _minimal_governance_lane_fragment(),
        _minimal_policy_doc_fragment(mention_governance_gates=False),
        failures,
    )
    assert any("prose should mention `Governance Gates`" in m for m in failures)


def test_evaluate_required_check_policy_fails_when_doc_missing_fast_required() -> None:
    mod = _load_policy_module()
    policy = """
## Required on Pull Requests

- `PR Compatibility Smoke (Linux, py3.12)`

Governance Gates
"""
    failures: list[str] = []
    mod.evaluate_required_check_policy(
        _minimal_ci_yml_fragment(),
        _minimal_governance_lane_fragment(),
        policy,
        failures,
    )
    assert any("missing `Fast Required`" in m for m in failures)


def test_required_check_policy_gate_cli_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    tool = root / "tools" / "harness.py"
    proc = subprocess.run(
        [sys.executable, str(tool), "required-check-policy"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
