# ruff: noqa
from __future__ import annotations

# mypy: ignore-errors

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# SSOT for `python tools/harness.py test-governance` (was previously duplicated in `ci.yml` `run: |`).
GOVERNANCE_EXPLICIT_PYTEST_PATHS: tuple[str, ...] = (
    "tests/test_core/test_canonical_semantics.py",
    "tests/test_core/test_agent_feedback_reason_taxonomy_closure.py",
    "tests/test_core/test_session.py",
    "tests/test_core/test_session_replay_verifier_malformed_shapes.py",
    "tests/test_core/test_session_workflow_strict_happy_path.py",
    "tests/test_core/test_replay_registry_closure_binding.py",
    "tests/test_core/test_replay_registry_closure_parity_all_entrypoints.py",
    "tests/test_core/test_chain_adapter_profiles.py",
    "tests/test_core/test_hook_manager.py",
    "tests/test_core/test_hook_governance_async_contract_mode_parity.py",
    "tests/test_core/test_status_aggregation.py",
    "tests/test_core/test_config_governance_overlap_guards.py",
    "tests/test_core/test_simulate_only_prior_validate_config.py",
    "tests/test_core/test_entrypoints.py",
    "tests/test_core/test_entrypoint_symbol_binding_contract.py",
    "tests/test_core/test_public_exports_contract.py",
    "tests/test_core/test_cli_public_contract.py",
    "tests/test_core/test_readme_envelope_contract.py",
    "tests/test_core/test_governance_provenance_matrix.py",
    "tests/test_layers/test_l4_rpc_manager_disagreement_report.py",
    "tests/test_layers/test_shadow_auditor_policy_bundle.py",
    "tests/test_integrations/test_langchain_tool_run_arun_delegate_to_guardian_paths.py",
)

_PR_COMPAT_SMOKE_PYTEST_PATHS: tuple[str, ...] = (
    "tests/test_core/test_entrypoints.py",
    "tests/test_core/test_sync_async_contract_consistency.py",
    "tests/test_core/test_registry_authority_contract.py",
)


def _run_repo_command(argv: list[str]) -> int:
    proc = subprocess.run(argv, cwd=_REPO_ROOT, check=False)
    return int(proc.returncode)


def check_lint() -> int:
    return _run_repo_command([sys.executable, "-m", "ruff", "check", "."])


def check_format_check() -> int:
    return _run_repo_command([sys.executable, "-m", "black", "--check", "."])


def check_typecheck() -> int:
    return _run_repo_command([sys.executable, "-m", "mypy", "--strict", "lirix"])


def check_test_governance() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", *GOVERNANCE_EXPLICIT_PYTEST_PATHS]
    return _run_repo_command(cmd)


def check_test_coverage_required() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--cov=lirix",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=xml",
    ]
    return _run_repo_command(cmd)


def check_test_pr_compat_smoke() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", *PR_COMPAT_SMOKE_PYTEST_PATHS]
    return _run_repo_command(cmd)


def check_test_compat_matrix() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-m",
        "not slow and not e2e and not network and not perf and not migration",
    ]
    return _run_repo_command(cmd)


def check_import_topology() -> int:
    return _run_repo_command(
        [sys.executable, str(_REPO_ROOT / "tools/gen_lirix_import_graph.py"), "--check"]
    )


def check_release_notes_gate() -> int:
    text = (_REPO_ROOT / "docs" / "release_notes.md").read_text(encoding="utf-8")
    needles = ("API Contract Delta", "additive and backward compatible")
    missing = [n for n in needles if n not in text]
    if missing:
        for item in missing:
            print(f"release-notes-gate: missing `{item}` in docs/release_notes.md", file=sys.stderr)
        return 1
    print("release-notes-gate: ok")
    return 0


def check_migration_observability_report() -> int:
    return _run_repo_command(
        [sys.executable, str(_REPO_ROOT / "tools/migration_observability_report.py")]
    )


def check_hygiene() -> int:
    import fnmatch
    import os
    import re
    import subprocess
    import sys
    from dataclasses import dataclass

    _SIGNOFF_DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    @dataclass(frozen=True)
    class Failure:
        title: str
        details: list[str]

    FORBIDDEN_TRACKED_GLOBS: tuple[str, ...] = (
        # Virtualenvs
        ".venv/**",
        ".venv*/**",
        "venv/**",
        "env/**",
        "site-packages/**",
        # Caches / build artifacts
        "**/__pycache__/**",
        ".pytest_cache/**",
        ".mypy_cache/**",
        ".ruff_cache/**",
        ".tox/**",
        ".nox/**",
        "htmlcov/**",
        # Coverage artifacts
        ".coverage",
        ".coverage.*",
        "coverage.xml",
    )

    AUDIT_ROOT = "audit_artifacts/"
    ALLOWED_AUDIT_PREFIX = "audit_artifacts/release_signoff/"

    SIGNOFF_REQUIRED_FILES: tuple[str, ...] = (
        "B4_local_ci_equivalent_brief.md",
        "R1_deprecation_warning_baseline.md",
        "C5_coverage_100_verification.md",
    )

    SIGNOFF_REQUIRED_GLOBS_ANY: tuple[str, ...] = (
        "B4_governance_gate_explicit_pytest*.log",
        "C4_full_pytest_warnings_baseline*.log",
        "B4_pytest_full_cov*.log",
        "B4_release_notes_gate_*.log",
        "B4_release_acceptance_report_*.json",
    )

    def _run_git(args: list[str]) -> str:
        p = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C"},
        )
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed:\n{p.stderr.strip()}")
        return p.stdout

    def _tracked_files() -> list[str]:
        out = _run_git(["ls-files", "-z"])
        if not out:
            return []
        parts = out.split("\0")
        return [p for p in parts if p]

    def _matches_any(path: str, globs: tuple[str, ...]) -> bool:
        return any(fnmatch.fnmatch(path, g) for g in globs)

    def main() -> int:
        tracked = _tracked_files()
        failures: list[Failure] = []

        forbidden = sorted({p for p in tracked if _matches_any(p, FORBIDDEN_TRACKED_GLOBS)})
        if forbidden:
            failures.append(
                Failure(
                    title="Forbidden tracked artifacts detected",
                    details=forbidden,
                )
            )

        audit_outside_allowlist = sorted(
            {
                p
                for p in tracked
                if p.startswith(AUDIT_ROOT) and not p.startswith(ALLOWED_AUDIT_PREFIX)
            }
        )
        if audit_outside_allowlist:
            failures.append(
                Failure(
                    title="Tracked audit artifacts outside allowlist",
                    details=audit_outside_allowlist,
                )
            )

        signoff_files = [p for p in tracked if p.startswith(ALLOWED_AUDIT_PREFIX)]
        date_dirs: set[str] = set()
        for p in signoff_files:
            # audit_artifacts/release_signoff/<YYYY-MM-DD>/...
            # (ignore loose files under release_signoff/)
            parts = Path(p).parts
            if len(parts) >= 4 and _SIGNOFF_DATE_DIR.match(parts[2]):
                # parts[0]=audit_artifacts, parts[1]=release_signoff, parts[2]=<date>
                date_dirs.add("/".join(parts[:3]) + "/")

        for date_dir in sorted(date_dirs):
            present = {p.removeprefix(date_dir) for p in signoff_files if p.startswith(date_dir)}

            missing_required = [f for f in SIGNOFF_REQUIRED_FILES if f not in present]
            if missing_required:
                failures.append(
                    Failure(
                        title=f"Sign-off bundle missing required files: {date_dir}",
                        details=missing_required,
                    )
                )

            required_glob_hits = [
                g for g in SIGNOFF_REQUIRED_GLOBS_ANY if any(fnmatch.fnmatch(x, g) for x in present)
            ]
            missing_globs = [g for g in SIGNOFF_REQUIRED_GLOBS_ANY if g not in required_glob_hits]
            if missing_globs:
                failures.append(
                    Failure(
                        title=f"Sign-off bundle missing required evidence logs: {date_dir}",
                        details=missing_globs,
                    )
                )

        if failures:
            sys.stderr.write("HYGIENE GATE FAILED\n")
            for f in failures:
                sys.stderr.write(f"\n== {f.title} ==\n")
                for line in f.details:
                    sys.stderr.write(f"- {line}\n")
            return 2

        print("Hygiene gate passed.")
        return 0

    return int(main())


def check_repo_exclusions_alignment() -> int:
    import re
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    SSOT = "docs/repo_exclusions.md"
    _AUDIT_MAP = ROOT / "docs" / "audit_path_map.md"
    _MARKERS = ("tdsc", "mantle_TT")

    def _fail(msg: str) -> int:
        print(msg, file=sys.stderr)
        print(f"See {SSOT} for the four-way alignment rule.", file=sys.stderr)
        return 1

    def _path_or_doc_token(text: str, marker: str) -> bool:
        """Require path-shaped or quoted-list markers, not arbitrary substrings (e.g. prose mentioning tdsc)."""
        if f"{marker}/" in text:
            return True
        if f"`{marker}/`" in text:
            return True
        if f"**`{marker}/`**" in text:
            return True
        if f'"{marker}"' in text:
            return True
        return False

    def _audit_scope_mentions_exclusions(audit_text: str) -> tuple[bool, str]:
        if "## Scope / Exclusions" not in audit_text and "Scope / Exclusions" not in audit_text:
            return False, "docs/audit_path_map.md: missing Scope / Exclusions section heading"
        if not _path_or_doc_token(audit_text, "tdsc") or not _path_or_doc_token(
            audit_text, "mantle_TT"
        ):
            return (
                False,
                "docs/audit_path_map.md: Scope must cite path-style exclusions for tdsc and mantle_TT "
                "(e.g. `tdsc/`, `mantle_TT/`)",
            )
        return True, ""

    def main() -> int:
        failures: list[str] = []

        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for m in _MARKERS:
            if not _path_or_doc_token(gitignore, m):
                failures.append(
                    f".gitignore: expected path or quoted-list token for `{m}/` (got strict match)"
                )

        harness = (ROOT / ".harnessignore").read_text(encoding="utf-8")
        for m in _MARKERS:
            if not _path_or_doc_token(harness, m):
                failures.append(f".harnessignore: expected path token `{m}/`")

        repo_doc = (ROOT / "docs" / "repo_exclusions.md").read_text(encoding="utf-8")
        for m in _MARKERS:
            if not _path_or_doc_token(repo_doc, m):
                failures.append(f"docs/repo_exclusions.md: expected path or table token for `{m}`")

        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(
            r"\[tool\.pytest\.ini_options\](?:.|\n)*?norecursedirs\s*=\s*\[(.*?)\]",
            pyproject,
            re.DOTALL,
        )
        if not m:
            failures.append(
                "pyproject.toml: could not find [tool.pytest.ini_options] norecursedirs"
            )
        else:
            block = m.group(1)
            if not all(tok in block for tok in ('"tdsc"', '"mantle_TT"')):
                failures.append(
                    "pyproject.toml: norecursedirs must list string entries "
                    '`"tdsc"` and `"mantle_TT"`'
                )

        if _AUDIT_MAP.is_file():
            audit_text = _AUDIT_MAP.read_text(encoding="utf-8")
            ok, reason = _audit_scope_mentions_exclusions(audit_text)
            if not ok:
                failures.append(reason)
        else:
            failures.append("docs/audit_path_map.md: missing file (audit scope cross-check)")

        if failures:
            return _fail("REPO EXCLUSIONS ALIGNMENT GATE FAILED:\n- " + "\n- ".join(failures))

        print("Repo exclusions alignment gate passed.")
        return 0

    return int(main())


def check_branch_protection_drift() -> int:
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    from typing import Tuple

    _TOOLS_DIR = Path(__file__).resolve().parents[1]
    if str(_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(_TOOLS_DIR))

    from ci_gate_shared import (
        doc_check_satisfied,
        parse_doc_required_checks,
        parse_workflow_job_names,
    )

    def _fetch_branch_protection_required_checks() -> Tuple[set[str], str]:
        repo = os.getenv("GITHUB_REPOSITORY")
        token = os.getenv("GITHUB_TOKEN")
        if not repo or not token:
            return set(), "skipped:no_token_or_repo"
        cmd = [
            "gh",
            "api",
            f"repos/{repo}/branches/main/protection/required_status_checks",
            "--jq",
            ".checks[].context",
        ]
        try:
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            return set(), "skipped:gh_not_installed"
        if proc.returncode != 0:
            return set(), "skipped:gh_api_failed"
        return {line.strip() for line in proc.stdout.splitlines() if line.strip()}, "checked"

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        doc = (root / "docs" / "branch_protection_required_checks.md").read_text(encoding="utf-8")
        ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        doc_required = parse_doc_required_checks(doc)
        workflow_names = parse_workflow_job_names(ci)
        missing = sorted(x for x in doc_required if not doc_check_satisfied(x, workflow_names))
        if missing:
            raise SystemExit(f"Documented required checks missing in workflow: {missing}")

        live_required, live_status = _fetch_branch_protection_required_checks()
        if live_status == "checked" and live_required != doc_required:
            raise SystemExit(
                "Branch protection required checks drift detected: "
                f"doc={sorted(doc_required)} live={sorted(live_required)}"
            )

        print(
            json.dumps(
                {
                    "ok": True,
                    "required_checks": sorted(doc_required),
                    "live_check": live_status,
                },
                ensure_ascii=True,
            )
        )
        return 0

    return int(main())


def check_ci_lane_responsibility() -> int:
    import sys
    from pathlib import Path

    _TOOLS_DIR = Path(__file__).resolve().parents[1]
    if str(_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(_TOOLS_DIR))

    from ci_gate_shared import (
        doc_check_satisfied,
        extract_job_if_conditions,
        parse_doc_required_checks,
        parse_workflow_job_names,
    )

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        ci_text = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        checks_doc = (root / "docs" / "branch_protection_required_checks.md").read_text(
            encoding="utf-8"
        )

        job_conditions = extract_job_if_conditions(ci_text)
        required_doc_checks = parse_doc_required_checks(checks_doc)
        workflow_job_names = parse_workflow_job_names(ci_text)
        assert "fast_required" in job_conditions
        assert "coverage_required" in job_conditions
        assert "compatibility_matrix" in job_conditions
        assert "pr_compat_smoke" in job_conditions

        assert job_conditions["coverage_required"] == "github.event_name != 'pull_request'"
        assert job_conditions["compatibility_matrix"] == "github.event_name != 'pull_request'"
        assert job_conditions["pr_compat_smoke"] == "github.event_name == 'pull_request'"
        # Doc contract: this file must clearly describe PR required checks vs non-PR slow lane.
        assert "## Required on Pull Requests" in checks_doc
        assert "## Non-PR Slow Lane" in checks_doc
        assert "## Governance Rule" in checks_doc
        assert "Coverage Required (Single Authority)" in checks_doc
        assert "Compatibility Matrix (...)" in checks_doc
        assert "Fast Required" in required_doc_checks
        assert any(c.startswith("PR Compatibility Smoke") for c in required_doc_checks)
        assert doc_check_satisfied("Fast Required", workflow_job_names)
        assert doc_check_satisfied("PR Compatibility Smoke", workflow_job_names)
        print("CI lane responsibility contract OK")
        return 0

    return int(main())


def check_required_check_policy() -> int:
    import sys
    from pathlib import Path

    _TOOLS_DIR = Path(__file__).resolve().parent
    if str(_TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(_TOOLS_DIR))

    from ci_gate_shared import evaluate_required_check_policy

    ROOT = Path(__file__).resolve().parents[1]
    CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
    GOVERNANCE_LANE_PATH = ROOT / ".github" / "workflows" / "governance-lane.yml"
    POLICY_DOC_PATH = ROOT / "docs" / "branch_protection_required_checks.md"

    def main() -> int:
        failures: list[str] = []
        ci_text = CI_PATH.read_text(encoding="utf-8")
        gov_text = GOVERNANCE_LANE_PATH.read_text(encoding="utf-8")
        policy_text = POLICY_DOC_PATH.read_text(encoding="utf-8")
        evaluate_required_check_policy(
            ci_text,
            gov_text,
            policy_text,
            failures,
            governance_lane_rel_path=str(GOVERNANCE_LANE_PATH.relative_to(ROOT)),
            policy_doc_rel_path=str(POLICY_DOC_PATH.relative_to(ROOT)),
        )
        if failures:
            for item in failures:
                print(item)
            return 1
        return 0

    return int(main())


def check_compat_switch_expiry() -> int:
    import os
    import sys
    from datetime import date
    from pathlib import Path
    from typing import Any

    ROOT = Path(__file__).resolve().parents[1]
    EXPIRY = date(2026, 6, 30)

    class _GatePlugin:
        name = "gate_probe"

        def can_handle(self, *, selector: bytes, to_address: str) -> bool:
            return False

        def decode_and_collect(self, *, selector: bytes, body: bytes, payload: dict) -> dict:
            return {}

    def _resolve_today() -> date:
        raw = str(os.getenv("LIRIX_COMPAT_GATE_TODAY", "")).strip()
        return date.fromisoformat(raw) if raw else date.today()

    def _assert_empty_decoder_plugins_fail_closed(
        *,
        ChainAdapter: Any,
        build_chain_profile: Any,
        DecoderRegistry: Any,
        ConfigurationGuardException: Any,
    ) -> list[str]:
        failures: list[str] = []
        registry = DecoderRegistry()
        registry.register(_GatePlugin())
        for policy in ("profile_allowlist", "compat_enable_all"):
            profile_cfg: dict[str, object] = {"decoder_plugins": []}
            if policy != "profile_allowlist":
                profile_cfg["decoder_policy"] = policy
            profile = build_chain_profile(1, profile_cfg)
            try:
                ChainAdapter(profile, decoder_registry=registry, strict_mode=True)
            except ConfigurationGuardException as exc:
                if exc.context.get("reason") != "decoder_plugins_required":
                    failures.append(
                        f"empty decoder_plugins guard reason drift for policy={policy}: {exc.context}"
                    )
            else:
                failures.append(f"empty decoder_plugins unexpectedly accepted for policy={policy}")
        return failures

    def _assert_compat_policy_expired(
        today: date,
        *,
        ChainAdapter: Any,
        build_chain_profile: Any,
        DecoderRegistry: Any,
        ConfigurationGuardException: Any,
    ) -> list[str]:
        if today <= EXPIRY:
            return []
        registry = DecoderRegistry()
        registry.register(_GatePlugin())
        profile = build_chain_profile(
            1,
            {
                "decoder_policy": "compat_enable_all",
                "decoder_plugins": ["gate_probe"],
            },
        )
        try:
            ChainAdapter(profile, decoder_registry=registry, strict_mode=True)
        except ConfigurationGuardException:
            return []
        return [
            "compat-switch expired "
            f"({EXPIRY.isoformat()}): compat_enable_all runtime path is still reachable"
        ]

    def main() -> int:
        try:
            from lirix.core.chain_adapter import ChainAdapter, build_chain_profile
            from lirix.core.decoder_registry import DecoderRegistry
            from lirix.core.exceptions import ConfigurationGuardException

            today = _resolve_today()
            lirix_imports = {
                "ChainAdapter": ChainAdapter,
                "build_chain_profile": build_chain_profile,
                "DecoderRegistry": DecoderRegistry,
                "ConfigurationGuardException": ConfigurationGuardException,
            }
            failures = _assert_empty_decoder_plugins_fail_closed(**lirix_imports)
            failures.extend(_assert_compat_policy_expired(today, **lirix_imports))
        except ImportError:
            sys.stderr.write(
                "compat_switch_expiry_gate: cannot import `lirix` (install the package in editable "
                'mode from the repo root: `python -m pip install -e ".[dev]"`).\n'
            )
            return 2
        if failures:
            for failure in failures:
                print(failure)
            return 1
        print(f"compat-switch gate ok (expiry={EXPIRY.isoformat()}, today={today.isoformat()})")
        return 0

    return int(main())


def check_plan_to_pr_exit_metrics() -> int:
    import json
    from pathlib import Path

    def _as_number(value: object) -> float:
        assert isinstance(value, (int, float))
        return float(value)

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        data = json.loads(
            (root / "docs" / "plan_to_pr_exit_metrics.json").read_text(encoding="utf-8")
        )
        assert data.get("version") == "1.0"
        assert isinstance(data.get("window_days"), int) and data["window_days"] > 0
        assert isinstance(data.get("generated_at"), str) and data["generated_at"].strip()

        metrics = data.get("metrics")
        assert isinstance(metrics, dict)

        pr = metrics.get("pr_required_latency_minutes")
        assert isinstance(pr, dict)
        assert _as_number(pr.get("value")) >= 0.0
        assert _as_number(pr.get("target_leq")) > 0.0
        _as_number(pr.get("trend_vs_prev_window_minutes"))

        main = metrics.get("main_full_coverage_latency_minutes")
        assert isinstance(main, dict)
        assert _as_number(main.get("value")) >= 0.0
        assert _as_number(main.get("target_leq")) > 0.0
        _as_number(main.get("trend_vs_prev_window_minutes"))

        failures = metrics.get("gate_failures")
        assert isinstance(failures, dict)
        assert isinstance(failures.get("total"), int) and failures["total"] >= 0
        assert isinstance(failures.get("target_leq"), int) and failures["target_leq"] >= 0
        assert isinstance(failures.get("trend_vs_prev_window_count"), int)
        by_category = failures.get("by_category")
        assert isinstance(by_category, dict) and by_category
        assert all(isinstance(k, str) and k.strip() for k in by_category)
        assert all(isinstance(v, int) and v >= 0 for v in by_category.values())

        admission = data.get("admission")
        assert isinstance(admission, dict)
        required = admission.get("required")
        assert isinstance(required, list) and required
        assert all(isinstance(rule, str) and rule.strip() for rule in required)
        status = admission.get("status")
        assert status in {"pass", "fail"}

        computed_pass = (
            _as_number(pr["value"]) <= _as_number(pr["target_leq"])
            and _as_number(main["value"]) <= _as_number(main["target_leq"])
            and int(failures["total"]) <= int(failures["target_leq"])
        )
        assert (
            status == "pass"
        ) == computed_pass, "admission status is inconsistent with metric thresholds"
        print("Plan-to-PR exit metrics contract OK")
        return 0

    return int(main())


def check_audit_internal_link() -> int:
    import re
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    DOCS = ROOT / "docs"

    # Markdown files scanned for outbound links to docs/*.md with #fragments.
    SOURCES = (
        DOCS / "architecture_control_plane.md",
        DOCS / "audit_path_map.md",
        DOCS / "api_reference.md",
        DOCS / "quickstart.md",
        ROOT / "README.md",
    )

    # Regex: capture target path and optional fragment from (...) in markdown links.
    _LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(#[^)\s]+)?\)")

    def _github_heading_slug(title: str) -> str:
        """Approximate GitHub/markdown heading anchor for ``title`` (without leading # marks)."""
        t = title.strip().lower()
        # Drop punctuation (keep word chars, whitespace, hyphen, underscore); then spaces -> hyphens.
        t = re.sub(r"[^\w\s\-]", "", t, flags=re.UNICODE)
        t = re.sub(r"\s+", "-", t)
        t = re.sub(r"-+", "-", t)
        return t.strip("-")

    def _heading_slugs(md_text: str) -> set[str]:
        slugs: set[str] = set()
        for line in md_text.splitlines():
            m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if not m:
                continue
            slugs.add(_github_heading_slug(m.group(2)))
        return slugs

    def _resolve_target(href_path: str, source_file: Path) -> Path | None:
        if href_path.startswith(("http://", "https://", "mailto:")):
            return None
        if href_path.startswith("/"):
            return None
        base = source_file.parent
        candidate = (base / href_path).resolve()
        try:
            candidate.relative_to(DOCS.resolve())
        except ValueError:
            return None
        return candidate if candidate.suffix.lower() == ".md" else None

    def main() -> int:
        failures: list[str] = []
        for src in SOURCES:
            if not src.exists():
                failures.append(f"missing source `{src.relative_to(ROOT)}`")
                continue
            text = src.read_text(encoding="utf-8")
            for href, frag in _LINK_RE.findall(text):
                target = _resolve_target(href, src)
                if target is None:
                    continue
                if not target.is_file():
                    failures.append(
                        f"{src.relative_to(ROOT)}: broken link `{href}` "
                        f"(resolved `{target.relative_to(ROOT)}`)"
                    )
                    continue
                if not frag:
                    continue
                slug = frag.lstrip("#")
                doc_slugs = _heading_slugs(target.read_text(encoding="utf-8"))
                if slug not in doc_slugs:
                    failures.append(
                        f"{src.relative_to(ROOT)}: fragment `{frag}` not found in "
                        f"`{target.relative_to(ROOT)}` (slug set missing `{slug}`)"
                    )

        if failures:
            for msg in failures:
                print(msg)
            return 1
        return 0

    return int(main())


def check_doc_preamble_hygiene() -> int:
    import argparse
    import re
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]

    _EN_HEADING = re.compile(r"^## English(\b| —|\s|$)", re.MULTILINE)
    _ZH_HEADING = re.compile(r"^## 中文\b", re.MULTILINE)
    _CH_LABEL = re.compile(r"^\*\*中文：\*\*")
    _CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

    def _line_no(text: str, pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    def _scan(text: str, rel: str) -> list[str]:
        warns: list[str] = []
        en_iter = list(_EN_HEADING.finditer(text))
        zh_iter = list(_ZH_HEADING.finditer(text))
        if not en_iter:
            return warns

        first_en = en_iter[0].start()
        last_en = en_iter[-1].start()

        if zh_iter:
            first_zh = zh_iter[0].start()
            if first_zh <= first_en:
                warns.append(
                    f"{rel}: first `## 中文` (L{_line_no(text, first_zh)}) should follow "
                    f"first `## English` (L{_line_no(text, first_en)})"
                )
            if first_zh < last_en:
                warns.append(
                    f"{rel}: first `## 中文` (L{_line_no(text, first_zh)}) precedes last "
                    f"`## English` (L{_line_no(text, last_en)})"
                )

        head = text[:first_en]
        for i, line in enumerate(head.splitlines(), start=1):
            if _CH_LABEL.search(line):
                warns.append(f"{rel}: `**中文：**` line before first `## English` (L{i})")

        for i, line in enumerate(head.splitlines(), start=1):
            if i == 1:
                continue
            stripped = line.strip()
            if not stripped or stripped == "---":
                continue
            if stripped.startswith("**EN:**") or stripped.startswith("> **EN:**"):
                continue
            if _CJK.search(line):
                warns.append(
                    f"{rel}: CJK on line {i} above first `## English` "
                    f"(move to `## 中文` or use English-only preamble)"
                )
                break

        return warns

    def main() -> int:
        ap = argparse.ArgumentParser(description=__doc__)
        ap.add_argument(
            "--enforce",
            action="store_true",
            help="exit 1 if any scanned file has violations",
        )
        ap.add_argument(
            "--quiet",
            action="store_true",
            help="suppress stderr warnings (still sets exit code with --enforce)",
        )
        ap.add_argument(
            "paths",
            nargs="*",
            help="repo-relative Markdown files (default: quickstart-style guides under docs/)",
        )
        args = ap.parse_args()
        default = (
            "docs/quickstart.md",
            "docs/troubleshooting.md",
            "docs/best_practices.md",
            "docs/api_reference.md",
        )
        rels = args.paths if args.paths else default

        all_warns: list[str] = []
        for rel in rels:
            path = ROOT / rel
            if not path.is_file():
                msg = f"{rel}: file not found"
                all_warns.append(msg)
                if not args.quiet:
                    print(msg, file=sys.stderr)
                continue
            text = path.read_text(encoding="utf-8")
            for w in _scan(text, rel):
                all_warns.append(w)
                if not args.quiet:
                    print(f"doc_preamble_hygiene: {w}", file=sys.stderr)

        if args.enforce and all_warns:
            return 1
        return 0

    return int(main())


def check_no_internal_imports() -> int:
    import ast
    import os
    import re
    import sys
    from dataclasses import dataclass
    from datetime import date
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]

    DEFAULT_SCAN_DIRS = ("docs", "examples", "tests", "tools")
    DEFAULT_SCAN_FILES = ("README.md", "CONTRIBUTING.md")

    ALLOWLIST_PATH = ROOT / "tests" / "INTERNAL_IMPORT_ALLOWLIST.txt"

    FORBIDDEN_MODULE_PREFIXES: tuple[str, ...] = ("lirix._client_core",)

    _MD_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+(lirix\.(?:_client_core)(?:\.[\w_]+)?)\b")

    @dataclass(frozen=True)
    class AllowItem:
        relpath: str
        expires: date
        reason: str

    def _load_allowlist(path: Path) -> tuple[dict[str, AllowItem], list[str]]:
        failures: list[str] = []
        items: dict[str, AllowItem] = {}
        if not path.is_file():
            return items, failures
        today = date.today()
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            rel = parts[0]
            meta = {
                k.strip(): v.strip() for k, v in (p.split("=", 1) for p in parts[1:] if "=" in p)
            }
            expires_s = meta.get("expires", "")
            reason = meta.get("reason", "")
            if not expires_s:
                failures.append(f"{rel}: allowlist entry missing expires=YYYY-MM-DD")
                continue
            if not reason:
                failures.append(f"{rel}: allowlist entry missing reason=...")
                continue
            try:
                expiry = date.fromisoformat(expires_s)
            except ValueError:
                failures.append(f"{rel}: invalid expires date `{expires_s}`")
                continue
            if expiry < today:
                failures.append(f"{rel}: allowlist entry expired on {expires_s}")
                continue
            items[rel] = AllowItem(relpath=rel, expires=expiry, reason=reason)
        return items, failures

    def _is_forbidden(module: str) -> bool:
        return any(module == p or module.startswith(p + ".") for p in FORBIDDEN_MODULE_PREFIXES)

    def _scan_python_imports(text: str, rel: str) -> list[str]:
        failures: list[str] = []
        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError:
            return failures
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden(alias.name):
                        failures.append(f"{rel}:{node.lineno}: forbidden import `{alias.name}`")
            elif isinstance(node, ast.ImportFrom):
                if node.module and _is_forbidden(node.module):
                    failures.append(f"{rel}:{node.lineno}: forbidden import-from `{node.module}`")
        return failures

    def _scan_markdown(text: str, rel: str) -> list[str]:
        failures: list[str] = []
        for i, line in enumerate(text.splitlines(), start=1):
            m = _MD_IMPORT_RE.search(line)
            if m:
                failures.append(f"{rel}:{i}: forbidden internal import mention `{m.group(1)}`")
        return failures

    def _iter_scan_paths(
        root: Path, scan_dirs: tuple[str, ...], scan_files: tuple[str, ...]
    ) -> list[Path]:
        out: list[Path] = []
        for d in scan_dirs:
            base = Path(d) if Path(d).is_absolute() else (root / d)
            if base.is_dir():
                out.extend(sorted(base.rglob("*")))
        for f in scan_files:
            p = root / f
            if p.is_file():
                out.append(p)
        return [p for p in out if p.is_file() and p.suffix.lower() in {".py", ".md"}]

    def main() -> int:
        allowlist, allow_failures = _load_allowlist(ALLOWLIST_PATH)
        failures: list[str] = list(allow_failures)

        scan_dirs_env = os.environ.get("NO_INTERNAL_IMPORTS_SCAN_DIRS", "")
        scan_dirs = (
            tuple(x.strip() for x in scan_dirs_env.split(",") if x.strip()) or DEFAULT_SCAN_DIRS
        )

        scan_files_env = os.environ.get("NO_INTERNAL_IMPORTS_SCAN_FILES", "")
        scan_files = (
            tuple(x.strip() for x in scan_files_env.split(",") if x.strip()) or DEFAULT_SCAN_FILES
        )

        for path in _iter_scan_paths(ROOT, scan_dirs=scan_dirs, scan_files=scan_files):
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            hits: list[str] = []
            if path.suffix.lower() == ".py":
                hits = _scan_python_imports(text, rel)
            elif path.suffix.lower() == ".md":
                hits = _scan_markdown(text, rel)
            if not hits:
                continue
            if rel in allowlist:
                continue
            failures.extend(hits)

        if failures:
            for msg in failures:
                print(msg)
            return 1
        print("no-internal-imports-gate: ok")
        return 0

    return int(main())


def check_root_import_surface() -> int:
    import ast
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    _SCAN_DIRS = ("tests", "examples", "tools")
    _SKIP_PATH_PARTS = frozenset({"tdsc", "mantle_TT"})

    def _should_skip(path: Path) -> bool:
        return bool(_SKIP_PATH_PARTS.intersection(path.parts))

    def _violations_in_tree(tree: ast.AST, *, allowed: frozenset[str], rel: str) -> list[str]:
        out: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "lirix":
                continue
            for alias in node.names:
                if alias.name == "*":
                    out.append(f"{rel}:{node.lineno}: forbidden `from lirix import *`")
                elif alias.name not in allowed:
                    out.append(
                        f"{rel}:{node.lineno}: `from lirix import {alias.name}` "
                        f"not in lirix.__all__ (use lirix.core / lirix.layers / …)"
                    )
        return out

    def main() -> int:
        sys.path.insert(0, str(ROOT))
        try:
            import lirix as lirix_pkg  # noqa: E402 — sys.path must be set first
        except ImportError:
            sys.stderr.write(
                "root_import_surface_gate: cannot import `lirix` (install in editable mode: "
                '`python -m pip install -e ".[dev]"`).\n'
            )
            return 2

        allowed = frozenset(lirix_pkg.__all__)
        failures: list[str] = []

        for dirname in _SCAN_DIRS:
            base = ROOT / dirname
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                if _should_skip(path):
                    continue
                rel = str(path.relative_to(ROOT))
                try:
                    src = path.read_text(encoding="utf-8")
                except OSError as exc:
                    failures.append(f"{rel}: read error {exc}")
                    continue
                try:
                    tree = ast.parse(src, filename=rel)
                except SyntaxError as exc:
                    failures.append(f"{rel}: syntax error {exc}")
                    continue
                failures.extend(_violations_in_tree(tree, allowed=allowed, rel=rel))

        if failures:
            for msg in failures:
                print(msg)
            return 1
        return 0

    return int(main())


def check_test_monkeypatch_convention() -> int:
    import argparse
    import re
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    SCAN_DIRS = ("tests", "examples")

    # Targets matching any prefix are OK.
    _ALLOWED_PREFIXES: tuple[str, ...] = (
        "lirix._client_core",
        "lirix.Lirix",
        "lirix._facade.Lirix",
        "lirix.core.orchestrator",
        "lirix.core.session",
        "lirix.layers.",
        "lirix.integrations.",
    )

    _LINE_RE = re.compile(
        r"(?:monkeypatch\.setattr|patch)\(\s*[\"'](lirix\.(?:[^\"']|\\.)+)[\"']",
    )

    # patch.object(lirix, ...) or monkeypatch.setattr(lirix, ...) — not ``lirix.Lirix``.
    _PATCH_PKG_OBJECT_RE = re.compile(
        r"(?:patch\.object|monkeypatch\.setattr)\s*\(\s*lirix\s*,",
    )

    def _ok_target(target: str) -> bool:
        return any(
            target.startswith(p) or target.startswith(p.rstrip(".")) for p in _ALLOWED_PREFIXES
        )

    def _scan_file(path: Path) -> list[tuple[int, str, str]]:
        hits: list[tuple[int, str, str]] = []
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return hits
        for i, line in enumerate(text.splitlines(), start=1):
            m = _LINE_RE.search(line)
            if m:
                target = m.group(1).replace("\\'", "'").replace('\\"', '"')
                if not _ok_target(target):
                    hits.append((i, line.strip(), target))
            if _PATCH_PKG_OBJECT_RE.search(line):
                hits.append(
                    (
                        i,
                        line.strip(),
                        "patch_pkg_object: use lirix.Lirix or lirix._client_core / submodule binding",
                    )
                )
        return hits

    def main() -> int:
        ap = argparse.ArgumentParser(description=__doc__)
        ap.add_argument(
            "--strict",
            action="store_true",
            help="exit with status 1 if any advisory warning is emitted",
        )
        args = ap.parse_args()
        warnings: list[str] = []
        for dirname in SCAN_DIRS:
            d = ROOT / dirname
            if not d.is_dir():
                continue
            for path in sorted(d.rglob("*.py")):
                for lineno, line, target in _scan_file(path):
                    rel = path.relative_to(ROOT)
                    msg = f"{rel}:{lineno}: unconventional patch target {target!r} — {line}"
                    warnings.append(msg)
                    print(msg, file=sys.stderr)

        if args.strict and warnings:
            return 1
        return 0

    return int(main())


def check_test_topology_admission() -> int:
    import json
    import os
    from datetime import date
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    ALLOWLIST = ROOT / "tests" / "MICRO_TEST_ALLOWLIST.txt"
    TARGET_DIRS = (ROOT / "tests" / "test_core", ROOT / "tests" / "test_layers")
    AUTH_BASELINE = ROOT / "docs" / "baselines" / "migration_observability_baseline.json"
    OBS_PREVIOUS = ROOT / "audit_artifacts" / "migration_observability" / "previous.json"
    STAGED_RATIO_BUDGETS: tuple[tuple[date, float], ...] = (
        (date(2026, 6, 15), 0.45),
        (date(2026, 7, 15), 0.40),
        (date(2099, 12, 31), 0.35),
    )

    def _load_allowlist() -> tuple[set[str], list[str]]:
        if not ALLOWLIST.is_file():
            return set(), []
        allowed: set[str] = set()
        failures: list[str] = []
        today = date.today()
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = [part.strip() for part in stripped.split("|")]
            rel = parts[0]
            expires = ""
            for meta in parts[1:]:
                if meta.startswith("expires="):
                    expires = meta.split("=", 1)[1].strip()
            if not expires:
                failures.append(f"{rel}: allowlist entry missing expires=YYYY-MM-DD metadata")
                continue
            try:
                expiry = date.fromisoformat(expires)
            except ValueError:
                failures.append(f"{rel}: invalid expires date `{expires}`")
                continue
            if expiry < today:
                failures.append(f"{rel}: allowlist exemption expired on {expires}")
                continue
            allowed.add(rel)
        return allowed, failures

    def _read_micro_ratio_from_payload(payload: object) -> float | None:
        if not isinstance(payload, dict):
            return None
        tests = payload.get("tests", {})
        if not isinstance(tests, dict):
            return None
        ratio = tests.get("micro_ratio")
        try:
            return float(ratio)
        except (TypeError, ValueError):
            return None

    def _read_micro_ratio_from_baseline(path: Path) -> float | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise ValueError("baseline json decode failed")
        ratio = _read_micro_ratio_from_payload(payload)
        if ratio is None:
            raise ValueError("baseline missing tests.micro_ratio")
        return ratio

    def _read_micro_ratio_from_previous(path: Path) -> float | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raise ValueError("previous json decode failed")
        ratio = _read_micro_ratio_from_payload(payload)
        if ratio is None:
            raise ValueError("previous missing tests.micro_ratio")
        return ratio

    def _current_ratio_budget(today: date) -> float:
        for deadline, budget in STAGED_RATIO_BUDGETS:
            if today <= deadline:
                return budget
        return STAGED_RATIO_BUDGETS[-1][1]

    def main() -> int:
        allowlist, failures = _load_allowlist()
        test_files = 0
        micro_files = 0
        for base in TARGET_DIRS:
            if not base.is_dir():
                continue
            for path in sorted(base.glob("test_*.py")):
                test_files += 1
                rel = path.relative_to(ROOT).as_posix()
                text = path.read_text(encoding="utf-8")
                test_count = sum(
                    1 for line in text.splitlines() if line.lstrip().startswith("def test_")
                )
                if test_count <= 1:
                    micro_files += 1
                if test_count <= 1 and rel not in allowlist:
                    failures.append(
                        f"{rel}: micro test file (<=1 test) is not in tests/MICRO_TEST_ALLOWLIST.txt"
                    )
        micro_ratio = (micro_files / test_files) if test_files else 0.0
        estimated_cost_seconds = (test_files * 1.2) + (micro_files * 0.5)
        failure_density = (len(failures) / test_files) if test_files else 0.0
        active_budget = _current_ratio_budget(date.today())
        if micro_ratio > active_budget:
            failures.append(f"micro_ratio={micro_ratio:.4f} exceeds budget={active_budget:.4f}")

        # Baseline authority order:
        #   1) frozen repo baseline (authoritative, reviewable)
        #   2) observability previous.json (best-effort, mutable)
        #   3) no baseline (warn-only)
        baseline_path = Path(os.environ.get("TEST_TOPOLOGY_BASELINE_PATH", str(AUTH_BASELINE)))
        previous_path = Path(os.environ.get("TEST_TOPOLOGY_PREVIOUS_PATH", str(OBS_PREVIOUS)))

        baseline_source = "none"
        baseline_ratio: float | None = None
        ci_mode = os.environ.get("CI") in {"1", "true", "True"}

        try:
            baseline_ratio = _read_micro_ratio_from_baseline(baseline_path)
            baseline_source = "authoritative_baseline"
        except ValueError as exc:
            if baseline_path.exists() and ci_mode:
                failures.append(f"baseline trust model: invalid authoritative baseline: {exc}")
            # Fall back to previous.json only if baseline is missing or invalid in non-CI mode.
            baseline_ratio = None

        if baseline_ratio is None:
            try:
                baseline_ratio = _read_micro_ratio_from_previous(previous_path)
                baseline_source = "observability_previous"
            except ValueError as exc:
                if previous_path.exists() and ci_mode:
                    failures.append(f"baseline trust model: invalid previous snapshot: {exc}")
                baseline_ratio = None

        if baseline_ratio is None:
            print(
                "topology-gate: warning: no readable baseline available; "
                "skipping micro_ratio regression check"
            )
        elif micro_ratio > baseline_ratio:
            failures.append(
                "micro_ratio regression: "
                f"current={micro_ratio:.4f} baseline={baseline_ratio:.4f} source={baseline_source}"
            )

        # CI cost-admission metrics (configurable by env; defaults keep local usage non-blocking).
        cost_budget = float(os.environ.get("TEST_TOPOLOGY_MAX_COST_SECONDS", "1000000"))
        density_budget = float(os.environ.get("TEST_TOPOLOGY_MAX_FAILURE_DENSITY", "1.0"))
        if estimated_cost_seconds > cost_budget:
            failures.append(
                f"ci_cost_budget exceeded: estimated_cost_seconds={estimated_cost_seconds:.2f} "
                f"budget={cost_budget:.2f}"
            )
        if failure_density > density_budget:
            failures.append(
                f"ci_failure_density exceeded: failure_density={failure_density:.4f} "
                f"budget={density_budget:.4f}"
            )
        if failures:
            for f in failures:
                print(f)
            return 1
        print(
            "topology-gate: ok "
            f"(test_files={test_files}, micro_files={micro_files}, micro_ratio={micro_ratio:.4f}, "
            f"baseline_source={baseline_source}, estimated_cost_seconds={estimated_cost_seconds:.2f}, "
            f"failure_density={failure_density:.4f})"
        )
        return 0

    return int(main())


def check_registry_authority_contract() -> int:
    import sys
    from pathlib import Path

    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT))

    def main() -> int:
        try:
            from lirix.core.exceptions import ConfigurationGuardException
            from lirix.core.registry_authority import (
                assert_registry_authority_contract,
                registry_authority_snapshot,
            )
        except ImportError:
            sys.stderr.write(
                "registry_authority_contract_gate: cannot import `lirix` (install in editable mode: "
                '`python -m pip install -e ".[dev]"`).\n'
            )
            return 2

        authority = registry_authority_snapshot(
            chain_registry={
                "UniswapV2Router02": "0x1111111111111111111111111111111111111111",
                "USDC": "0x2222222222222222222222222222222222222222",
            },
            decoder_registry={
                "erc20_transfer": "decoder://erc20/transfer",
                "uniswap_v2_swap": "decoder://uniswap/v2/swap",
            },
            source="offline_fixture",
        )
        try:
            assert_registry_authority_contract(authority)
        except ConfigurationGuardException as exc:
            print(f"registry-authority-gate: {exc.context}")
            return 1
        print("registry-authority-gate: ok (offline deterministic fixture)")
        return 0

    return int(main())


def check_legacy_sunset() -> int:
    import re
    from pathlib import Path

    def _parse_semver(version: str) -> tuple[int, int, int]:
        m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version.strip())
        assert m, f"invalid version: {version!r}"
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    def _extract_project_version(pyproject_text: str) -> str:
        # Minimal TOML extraction; repo already keeps `version = "x.y.z"` under [project].
        m = re.search(r'^\s*version\s*=\s*"(\d+\.\d+\.\d+)"\s*$', pyproject_text, re.M)
        assert m, "pyproject: missing [project].version"
        return m.group(1)

    def _extract_package_version(init_text: str) -> str:
        m = re.search(r'^\s*__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$', init_text, re.M)
        assert m, "lirix/__init__.py: missing __version__"
        return m.group(1)

    def _extract_sunset_target_version(doc_text: str) -> str:
        m = re.search(r"\*\*v(\d+\.\d+\.\d+)\s*\(sunset target\)\*\*", doc_text)
        assert m, "docs/legacy_sunset_milestones.md: missing sunset target version marker"
        return m.group(1)

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        legacy_tests = list((root / "tests" / "integrations").glob("test_*.py"))
        assert legacy_tests == [], "tests/integrations must remain empty after migration"

        pyproject_text = (root / "pyproject.toml").read_text(encoding="utf-8")
        init_text = (root / "lirix" / "__init__.py").read_text(encoding="utf-8")
        milestones_text = (root / "docs" / "legacy_sunset_milestones.md").read_text(
            encoding="utf-8"
        )
        assert "id=legacy-window-current" in milestones_text
        assert "id=legacy-window-enforcement" in milestones_text
        assert "id=legacy-window-final" in milestones_text
        assert "Automated Validation Path" in milestones_text

        project_version = _extract_project_version(pyproject_text)
        package_version = _extract_package_version(init_text)
        assert project_version == package_version, "version drift: pyproject vs lirix/__init__.py"

        sunset_target = _extract_sunset_target_version(milestones_text)
        v_current = _parse_semver(project_version)
        v_target = _parse_semver(sunset_target)
        assert v_current <= v_target, "package version exceeds legacy sunset target (docs drift)"

        root_exports = init_text
        assert "lirix.legacy" not in root_exports

        core_init_text = (root / "lirix" / "core" / "__init__.py").read_text(encoding="utf-8")
        assert "lirix.legacy" not in core_init_text

        legacy_pkg = root / "lirix" / "legacy"
        legacy_test_dir = root / "tests" / "test_legacy"
        assert not legacy_pkg.exists(), "lirix/legacy removed (canonical Lirix only)"
        assert not legacy_test_dir.exists(), "tests/test_legacy removed with legacy sunset"

        print("Legacy sunset gate OK")
        return 0

    return int(main())


def check_phase_exit_checklists() -> int:
    import json
    from pathlib import Path

    _EVIDENCE_PREFIXES = ("docs/", "tools/", "tests/", "lirix/", "examples/")

    def _validate_evidence_entry(*, root: Path, evidence: str) -> None:
        token = evidence.strip()
        assert token
        path_part, _, _symbol = token.partition("::")
        if path_part.startswith(_EVIDENCE_PREFIXES):
            target = root / path_part
            assert target.exists(), f"missing evidence path: {path_part}"

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        p = root / "docs" / "phase_exit_checklists.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("version") == "1.0"
        phases = data.get("phases")
        assert isinstance(phases, list) and phases
        for phase in phases:
            assert isinstance(phase, dict)
            assert isinstance(phase.get("id"), str) and phase["id"]
            assert isinstance(phase.get("name"), str) and phase["name"]
            checks = phase.get("checks")
            assert isinstance(checks, list) and checks
            for check in checks:
                assert isinstance(check, dict)
                assert isinstance(check.get("id"), str) and check["id"]
                evidence = check.get("evidence")
                assert isinstance(evidence, list) and evidence
                assert all(isinstance(x, str) and x.strip() for x in evidence)
                for item in evidence:
                    _validate_evidence_entry(root=root, evidence=item)
        print("Phase exit checklist contract OK")
        return 0

    return int(main())


def check_failure_surface_triage() -> int:
    import json
    import re
    from pathlib import Path

    ALLOWED_CATEGORIES = {"historical", "regression", "environment"}
    ALLOWED_STATUS = {"open", "triaged", "fixed", "wont_fix"}
    _MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
    _MARKDOWN_ANCHOR_RE = re.compile(
        r"""<a\s+[^>]*(?:id|name)\s*=\s*["']([^"']+)["'][^>]*>""",
        re.IGNORECASE,
    )

    def _slugify_markdown_heading(raw: str) -> str:
        """GitHub-style heading slug for local markdown anchor resolution."""
        text = raw.strip().lower()
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
        text = re.sub(r"[^\w\-\u4e00-\u9fff ]+", "", text)
        text = text.replace(" ", "-")
        text = re.sub(r"-{2,}", "-", text).strip("-")
        return text

    def _extract_markdown_anchors(markdown: str) -> set[str]:
        anchors: set[str] = set()
        for line in markdown.splitlines():
            for match in _MARKDOWN_ANCHOR_RE.finditer(line):
                anchors.add(match.group(1).strip().lower())
            heading = _MARKDOWN_HEADING_RE.match(line)
            if heading:
                slug = _slugify_markdown_heading(heading.group(2))
                if slug:
                    anchors.add(slug)
        return anchors

    def _validate_evidence_pointer(*, root: Path, evidence: str) -> None:
        pointer = evidence.strip()
        assert pointer
        rel_path, sep, anchor = pointer.partition("#")
        if rel_path.startswith(("docs/", "tools/", "tests/", "lirix/", "examples/")):
            target = root / rel_path
            assert target.exists(), f"missing evidence file: {rel_path}"
            if sep:
                assert target.suffix.lower() in {
                    ".md",
                    ".markdown",
                }, f"anchor pointer requires markdown target: {pointer}"
                anchors = _extract_markdown_anchors(target.read_text(encoding="utf-8"))
                assert anchor.strip().lower() in anchors, f"missing markdown anchor: {pointer}"

    def main() -> int:
        root = Path(__file__).resolve().parents[1]
        p = root / "docs" / "failure_surface_triage_57.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data.get("version") == "1.0"
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        target_failure_count = summary.get("target_failure_count")
        if target_failure_count is not None:
            assert isinstance(target_failure_count, int)
            assert target_failure_count > 0
        cases = data.get("cases")
        assert isinstance(cases, list)
        assert len(cases) > 0
        if isinstance(target_failure_count, int):
            assert len(cases) == target_failure_count

        owners: set[str] = set()
        statuses: set[str] = set()
        ids: set[str] = set()
        for case in cases:
            assert isinstance(case, dict)
            for key in ("id", "category", "owner", "status", "evidence"):
                assert key in case
            cid = case["id"]
            assert isinstance(cid, str) and cid.strip()
            assert cid not in ids
            ids.add(cid)
            assert case["category"] in ALLOWED_CATEGORIES
            assert case["status"] in ALLOWED_STATUS
            owner = case["owner"]
            assert isinstance(owner, str) and owner.strip()
            evidence = case["evidence"]
            assert isinstance(evidence, str) and evidence.strip()
            _validate_evidence_pointer(root=root, evidence=evidence)
            owners.add(owner.strip())
            statuses.add(str(case["status"]))
        # Minimal "truthiness" constraints: avoid empty shells and single-bucket dumping.
        assert len(owners) >= 2
        assert len(statuses) >= 2
        print("Failure surface triage contract OK")
        return 0

    return int(main())


def check_contract_manifest() -> int:
    from tools import contract_manifest_gate

    return contract_manifest_gate.check_contract_manifest()
