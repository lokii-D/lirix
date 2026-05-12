# ruff: noqa: SIM108
from __future__ import annotations

from typing import Optional


def extract_job_if_conditions(ci_text: str) -> dict[str, Optional[str]]:
    """Extract top-level `if:` from each workflow job block."""
    in_jobs = False
    current_job: Optional[str] = None
    result: dict[str, Optional[str]] = {}
    for raw in ci_text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw.startswith("jobs:"):
            in_jobs = True
            current_job = None
            continue
        if not in_jobs:
            continue
        if raw.startswith("  ") and not raw.startswith("    "):
            token = stripped
            if token.endswith(":") and " " not in token:
                current_job = token[:-1]
                result.setdefault(current_job, None)
            else:
                current_job = None
            continue
        if current_job and raw.startswith("    if:"):
            result[current_job] = raw.split("if:", 1)[1].strip()
    return result


def parse_doc_required_checks(doc_text: str) -> set[str]:
    checks: set[str] = set()
    in_required_section = False
    in_governance_rule_section = False
    for raw in doc_text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_required_section = line == "## Required on Pull Requests"
            in_governance_rule_section = line == "## Governance Rule"
            continue
        if line.startswith("#"):
            continue
        if in_governance_rule_section and line.startswith(
            "The branch-protection required checks MUST include:"
        ):
            continue
        if not (in_required_section or in_governance_rule_section):
            continue
        if line.startswith("- `") and "`" in line[3:]:
            checks.add(line.split("`")[1])
    return checks


def parse_workflow_job_names(ci_text: str) -> set[str]:
    names: set[str] = set()
    in_jobs = False
    current_job: Optional[str] = None
    for raw in ci_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("jobs:"):
            in_jobs = True
            current_job = None
            continue
        if not in_jobs:
            continue
        if raw.startswith("  ") and not raw.startswith("    "):
            token = raw.strip()
            if token.endswith(":") and " " not in token:
                current_job = token[:-1]
            else:
                current_job = None
            continue
        if current_job and raw.startswith("    name:"):
            names.add(raw.split("name:", 1)[1].strip())
            continue
    return names


def doc_check_satisfied(doc_check: str, workflow_names: set[str]) -> bool:
    if doc_check.startswith("PR Compatibility Smoke"):
        return any(n.startswith("PR Compatibility Smoke") for n in workflow_names)
    if doc_check.startswith("Compatibility Matrix"):
        return any(n.startswith("Compatibility Matrix") for n in workflow_names)
    return doc_check in workflow_names


def evaluate_required_check_policy(
    ci_text: str,
    governance_lane_text: str,
    policy_text: str,
    failures: list[str],
    *,
    governance_lane_rel_path: str = ".github/workflows/governance-lane.yml",
    policy_doc_rel_path: str = "docs/branch_protection_required_checks.md",
) -> None:
    """Append policy drift messages to *failures* (no I/O).

    Used by tests with workflow fragments.
    """

    def _require(condition: bool, message: str, bucket: list[str]) -> None:
        if not condition:
            bucket.append(message)

    job_conditions = extract_job_if_conditions(ci_text)
    doc_required_checks = parse_doc_required_checks(policy_text)
    workflow_job_names = parse_workflow_job_names(ci_text)
    governance_lane_job_names = parse_workflow_job_names(governance_lane_text)

    _require("pull_request:" in ci_text, "ci-policy: pull_request trigger missing", failures)
    _require(
        job_conditions.get("coverage_required") == "github.event_name != 'pull_request'",
        "ci-policy: coverage_required must remain non-PR (A+ strategy)",
        failures,
    )
    _require(
        job_conditions.get("pr_compat_smoke") == "github.event_name == 'pull_request'",
        "ci-policy: pr_compat_smoke pull_request job is required",
        failures,
    )
    _require(
        '"3.9"' in ci_text and '"3.14"' in ci_text,
        "ci-policy: PR compatibility matrix must include py3.9 and py3.14",
        failures,
    )
    _require(
        job_conditions.get("compatibility_matrix") == "github.event_name != 'pull_request'",
        "ci-policy: full compatibility_matrix should remain non-PR",
        failures,
    )

    _require(
        "Fast Required" in doc_required_checks,
        "required-check-policy-doc: missing `Fast Required`",
        failures,
    )
    _require(
        any(c.startswith("PR Compatibility Smoke") for c in doc_required_checks),
        "required-check-policy-doc: missing `PR Compatibility Smoke`",
        failures,
    )
    for check, label in (
        ("Fast Required", "Fast Required"),
        ("PR Compatibility Smoke", "PR Compatibility Smoke"),
    ):
        _require(
            doc_check_satisfied(check, workflow_job_names),
            f"required-check-policy-workflow: `{label}` missing from workflow job names",
            failures,
        )

    _require(
        "Governance Gates" in governance_lane_job_names,
        "required-check-policy-workflow: `Governance Gates` job name missing from "
        f"`{governance_lane_rel_path}`",
        failures,
    )
    _require(
        "Governance Gates" in policy_text,
        "required-check-policy-doc: prose should mention `Governance Gates` (non-PR lane; "
        f"see `{policy_doc_rel_path}` § Non-PR Slow Lane / job vs steps)",
        failures,
    )
