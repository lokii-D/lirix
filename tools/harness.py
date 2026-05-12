#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS_DIR = Path(__file__).resolve().parent
for _p in (_REPO_ROOT, _TOOLS_DIR):
    _token = str(_p)
    if _token not in sys.path:
        sys.path.insert(0, _token)

from tools import validators  # noqa: E402

COMMANDS = {
    "audit-internal-link": validators.check_audit_internal_link,
    "branch-protection-drift": validators.check_branch_protection_drift,
    "check-exclusions": validators.check_repo_exclusions_alignment,
    "ci-lane-responsibility": validators.check_ci_lane_responsibility,
    "compat-switch-expiry": validators.check_compat_switch_expiry,
    "contract-manifest": validators.check_contract_manifest,
    "doc-preamble-hygiene": validators.check_doc_preamble_hygiene,
    "failure-surface-triage": validators.check_failure_surface_triage,
    "hygiene": validators.check_hygiene,
    "legacy-sunset": validators.check_legacy_sunset,
    "no-internal-imports": validators.check_no_internal_imports,
    "phase-exit-checklists": validators.check_phase_exit_checklists,
    "plan-to-pr-exit-metrics": validators.check_plan_to_pr_exit_metrics,
    "registry-authority-contract": validators.check_registry_authority_contract,
    "required-check-policy": validators.check_required_check_policy,
    "root-import-surface": validators.check_root_import_surface,
    "test-monkeypatch-convention": validators.check_test_monkeypatch_convention,
    "test-topology-admission": validators.check_test_topology_admission,
}


def main(argv: list[str] | None = None) -> int:
    """Route to *validators* gates; gate-specific flags/paths follow the subcommand."""

    argv_use = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description="Unified harness gate router")
    parser.add_argument("command", choices=sorted(COMMANDS.keys()))
    args, rest = parser.parse_known_args(argv_use)
    saved = sys.argv
    prog = saved[0] if saved else str(Path(__file__).resolve())
    sys.argv = [prog, *rest]
    try:
        return int(COMMANDS[args.command]())
    finally:
        sys.argv = saved


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
