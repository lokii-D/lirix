# SPDX-License-Identifier: MIT
# ruff: noqa: E501
"""Contract manifest gate (extracted for harness parity + unit tests)."""

import ast
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]

# Display name of the step in `.github/workflows/ci.yml` whose `run: |` lists governance pytest files.
# Keep in sync with YAML; referenced by extraction, validation errors, and contract tests.
# `contract_manifest_gate` asserts a stripped `- name: …` line exactly matches this string in `ci.yml`
# (see `_assert_governance_explicit_step_line_in_ci_yml`) so renaming only the constant cannot drift
# from the workflow silently. See `docs/ci_gate_matrix.md` § **Docs contract gate** — governance pytest SSOT.
GOVERNANCE_GATE_EXPLICIT_STEP_NAME = "Governance gate (explicit)"

_TOOLS_GATES_INDEX_MAIN_ROW_RE = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|", re.MULTILINE)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _require_all(doc: str, name: str, needles: list[str], failures: list[str]) -> None:
    for needle in needles:
        if needle not in doc:
            failures.append(f"{name}: missing `{needle}`")


def _extract_governance_gate_tests(ci_yml: str) -> list[str]:
    """
    Extract the explicit governance gate test list from `.github/workflows/ci.yml` only.

    **Single-workflow assumption:** the exhaustive pytest path list is parsed only from
    ``.github/workflows/ci.yml`` (step ``GOVERNANCE_GATE_EXPLICIT_STEP_NAME``), not from
    ``governance-lane.yml`` or other workflows. If a second workflow later duplicates an
    explicit governance list, extend the extractor (or add a dedicated manifest) before
    relying on parity. See ``docs/ci_gate_matrix.md`` § **Docs contract gate**.

    This is a structured extraction (step name + run block), not a substring search.
    """
    lines = ci_yml.splitlines()
    in_gate = False
    in_run_block = False
    tests: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- name:") and GOVERNANCE_GATE_EXPLICIT_STEP_NAME in stripped:
            in_gate = True
            in_run_block = False
            continue
        if (
            in_gate
            and stripped.startswith("- name:")
            and GOVERNANCE_GATE_EXPLICIT_STEP_NAME not in stripped
        ):
            # next step begins
            break
        if in_gate and stripped == "run: |":
            in_run_block = True
            continue
        if in_gate and in_run_block:
            # run block ends when indentation collapses to step indentation
            if (
                stripped.startswith("- name:")
                or stripped.startswith("uses:")
                or stripped.startswith("run:")
            ):
                break
            token = stripped.rstrip("\\").strip()
            if token.startswith("tests/") and token.endswith(".py"):
                tests.append(token)
    return sorted(set(tests))


# Floor on the **count** of `tests/...py` lines in the step `GOVERNANCE_GATE_EXPLICIT_STEP_NAME`.
# Maintenance: when you add paths to that step in `ci.yml`, bump this constant to match the new
# minimum count so accidental truncation cannot slip under the floor. Also extend
# `_GOVERNANCE_GATE_CI_YML_ANCHORS` when adding new classes of governance coverage that must never
# disappear from CI. See `docs/ci_gate_matrix.md` § Fast Required / governance list.
_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS = 8
_GOVERNANCE_GATE_CI_YML_ANCHORS: tuple[str, ...] = (
    "tests/test_core/test_canonical_semantics.py",
    "tests/test_core/test_entrypoints.py",
    "tests/test_core/test_chain_adapter_profiles.py",
    "tests/test_core/test_cli_public_contract.py",
)


def _validate_governance_explicit_list(gated_tests: list[str], failures: list[str]) -> None:
    """Append failures when extracted list is empty, below floor, or missing anchor paths."""

    if not gated_tests:
        failures.append("ci-governance-gate: failed to extract explicit gate test list")
        return
    if len(gated_tests) < _GOVERNANCE_GATE_EXPLICIT_MIN_TESTS:
        failures.append(
            "ci-governance-gate: explicit gate list too short "
            f"({len(gated_tests)} < {_GOVERNANCE_GATE_EXPLICIT_MIN_TESTS}); "
            f"verify `.github/workflows/ci.yml` step `{GOVERNANCE_GATE_EXPLICIT_STEP_NAME}` "
            "and its `run: |` block were not renamed or truncated."
        )
    for t in _GOVERNANCE_GATE_CI_YML_ANCHORS:
        if t not in gated_tests:
            failures.append(f"ci-governance-gate: missing gated test `{t}`")


def _assert_governance_explicit_step_line_in_ci_yml(ci_yml: str, failures: list[str]) -> None:
    """Require a step line whose stripped form is exactly ``- name: {GOVERNANCE_GATE_EXPLICIT_STEP_NAME}``."""

    expected = f"- name: {GOVERNANCE_GATE_EXPLICIT_STEP_NAME}"
    for raw in ci_yml.splitlines():
        if raw.strip() == expected:
            return
    failures.append(
        "ci-governance-gate: `.github/workflows/ci.yml` has no step whose stripped `- name:` line "
        f"exactly matches `{expected!r}` (drift vs `GOVERNANCE_GATE_EXPLICIT_STEP_NAME` in this script). "
        "Rename the YAML step and the constant together. See `docs/ci_gate_matrix.md` § **Docs contract gate** "
        "— governance pytest SSOT."
    )


def _count_harness_gate_modules() -> int:
    harness_src = (ROOT / "tools" / "harness.py").read_text(encoding="utf-8")
    matches = re.findall(
        r'^\s+"([a-z0-9-]+)":\s+validators\.check_', harness_src, flags=re.MULTILINE
    )
    return len(matches)


def _count_tools_gates_index_main_table_rows(index_md: str) -> int:
    """Count ``| `<subcommand>` |`` data rows in the main table (content before ``## Related tools``)."""

    main, sep, _rest = index_md.partition("## Related tools")
    scan = main if sep else index_md
    return len(_TOOLS_GATES_INDEX_MAIN_ROW_RE.findall(scan))


def _validate_tools_gates_index_row_parity(index_md: str, failures: list[str]) -> None:
    """Drift guard: main index table row count matches ``tools/*.py`` gate modules."""

    disk = _count_harness_gate_modules()
    doc_rows = _count_tools_gates_index_main_table_rows(index_md)
    if disk != doc_rows:
        failures.append(
            "tools-gates-index-parity: `docs/tools_gates_index.md` main table lists "
            f"{doc_rows} harness subcommand row(s) but `tools/` has {disk} gate module(s). "
            "Update the doc table (or remove a stale row) so contributors see every gate. "
            "Related-only scripts belong under § **Related tools (not harness subcommands)**."
        )


# Assertions about exports / `__all__` / package surface may legitimately cite `lirix/__init__.py`.
_AUDIT_MAP_INIT_PY_ALLOWLIST_SUBSTRINGS: tuple[str, ...] = (
    "public export",
    "__all__",
    "entrypoint symbol",
    "version gate",
    "re-export",
)

# If the assertion column matches pipeline/replay/session semantics, `code_path` must not cite
# `lirix/__init__.py` alone as the implementation site (use `lirix/_facade.py` / `lirix/_client_facade.py`).
# Maintenance: when adding rows to `docs/audit_path_map.md` § Core Assertions Map for pipeline /
# replay / l1_l3 semantics, extend this regex if new keywords appear; run
# `python tools/harness.py contract-manifest` locally (also enforced in CI).
_AUDIT_MAP_INIT_PY_PIPELINE_TRIGGER = re.compile(
    r"(l1_l3_ok|\breplay\b|_build_rpc|replay_session|verify_replay_bundle|_mark_session)",
    re.IGNORECASE,
)


def _audit_map_client_core_paths(rows: list[dict[str, str]], failures: list[str]) -> None:
    """D2 heuristic: pipeline rows must not cite ``lirix/__init__.py`` as implementation."""

    for row in rows:
        assertion = row["assertion"]
        code_cell = row["code_path"]
        if "lirix/__init__.py" not in code_cell:
            continue
        if any(s.lower() in assertion.lower() for s in _AUDIT_MAP_INIT_PY_ALLOWLIST_SUBSTRINGS):
            continue
        if not _AUDIT_MAP_INIT_PY_PIPELINE_TRIGGER.search(assertion):
            continue
        failures.append(
            "audit_path_map.code_path: pipeline/replay assertion cites `lirix/__init__.py`; "
            "use `lirix/_facade.py` (Lirix facade) or `lirix/_client_facade.py` "
            "(replay helpers) — row assertion starts: "
            f"{assertion[:80]!r}"
        )


def _extract_audit_map_rows(md: str) -> list[dict[str, str]]:
    """
    Extract rows from the 'Core Assertions Map' markdown table.
    """
    lines = md.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## Core Assertions Map":
            start = i
            break
    if start is None:
        return []
    rows: list[dict[str, str]] = []
    in_table = False
    for line in lines[start:]:
        if line.strip().startswith("| Assertion |"):
            in_table = True
            continue
        if in_table and line.strip().startswith("| ---"):
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            break
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if len(parts) != 5:
            continue
        rows.append(
            {
                "assertion": parts[0],
                "code_path": parts[1],
                "test_path": parts[2],
                "evidence_keys": parts[3],
                "ci_gate": parts[4],
            }
        )
    return rows


def _extract_backticked_paths(cell: str) -> list[str]:
    # Backticked paths like `tests/foo.py`, allow multiple.
    return re.findall(r"`([^`]+)`", cell)


def _require_paths_exist(paths: list[str], *, failures: list[str], context: str) -> None:
    for p in paths:
        raw = p
        # Allow doc table to cite symbols like `file.py::symbol` or `file.py:function`.
        if "::" in raw:
            raw = raw.split("::", 1)[0]
        if ":" in raw and raw.endswith(".py") is False and raw.split(":", 1)[0].endswith(".py"):
            raw = raw.split(":", 1)[0]
        if raw.startswith(("lirix/", "tests/", "docs/", "tools/")) and not (ROOT / raw).exists():
            failures.append(f"{context}: missing path `{p}`")


def _assert_exception_inheritance_contract(
    *, api_doc: str, exceptions_source: str, failures: list[str]
) -> None:
    """Semantic check: docs and exception inheritance lattice must match."""
    try:
        tree = ast.parse(exceptions_source)
    except SyntaxError as exc:
        failures.append(f"exception-lattice: failed to parse exceptions source: {exc}")
        return
    alias_to_base: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if isinstance(node.value, ast.Name):
            alias_to_base[target.id] = node.value.id
        elif isinstance(node.value, ast.Attribute):
            alias_to_base[target.id] = node.value.attr

    def _canonical_base(name: str) -> str:
        seen: set[str] = set()
        current = name
        while current in alias_to_base and current not in seen:
            seen.add(current)
            current = alias_to_base[current]
        return current

    parents: dict[str, set[str]] = {}
    classes: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        classes.add(node.name)
        base_names: set[str] = set()
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.add(_canonical_base(base.id))
            elif isinstance(base, ast.Attribute):
                base_names.add(_canonical_base(base.attr))
        if base_names:
            parents[node.name] = base_names
    if "LirixSecurityException" not in parents:
        failures.append("exception-lattice: missing `LirixSecurityException` class")
        return
    if "LirixBaseException" not in parents.get("LirixSecurityException", set()):
        failures.append(
            "exception-lattice: `LirixSecurityException` must inherit `LirixBaseException`"
        )
    reverse_edges: dict[str, set[str]] = {}
    for child, bases in parents.items():
        for base in bases:
            reverse_edges.setdefault(base, set()).add(child)
    security_descendants: set[str] = set()
    stack = list(reverse_edges.get("LirixSecurityException", set()))
    while stack:
        item = stack.pop()
        if item in security_descendants:
            continue
        security_descendants.add(item)
        stack.extend(reverse_edges.get(item, set()))
    sec_children = sorted(security_descendants)
    base_children = sorted(
        name
        for name in classes
        if name != "LirixBaseException" and "LirixBaseException" in parents.get(name, set())
    )
    if not sec_children:
        failures.append("exception-lattice: security subtree is empty")
    # Guard against documentation drift ("all exceptions inherit security exception").
    if len(sec_children) == len(base_children):
        failures.append("exception-lattice: expected mixed tree, got security-only tree")
    required_doc_markers = [
        "仅安全相关子集继承自 `LirixSecurityException`",
        "only the security-oriented subset uses",
    ]
    for marker in required_doc_markers:
        if marker not in api_doc:
            failures.append(f"api-reference-exception-contract: missing `{marker}`")


def _assert_validate_and_simulate_return_contract(
    *, client_source: str, failures: list[str]
) -> None:
    """Gate validate_and_simulate return keys + semantic markers."""
    try:
        tree = ast.parse(client_source)
    except SyntaxError as exc:
        failures.append(f"validate-and-simulate-contract: parse failed: {exc}")
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "validate_and_simulate":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Call):
                    call = inner.value
                    if (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "_run_coroutine_sync"
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "self"
                        and call.args
                    ):
                        runner = call.args[0]
                        if (
                            isinstance(runner, ast.Lambda)
                            and isinstance(runner.body, ast.Call)
                            and isinstance(runner.body.func, ast.Attribute)
                            and runner.body.func.attr == "_run_full_pipeline"
                            and isinstance(runner.body.func.value, ast.Name)
                            and runner.body.func.value.id == "self"
                        ):
                            # Facade wraps async orchestration: sync entry delegates via
                            # `_run_coroutine_sync(lambda: self._run_full_pipeline(...))`.
                            return
                        if (
                            isinstance(runner, ast.Call)
                            and isinstance(runner.func, ast.Attribute)
                            and runner.func.attr == "_run_full_pipeline"
                            and isinstance(runner.func.value, ast.Name)
                            and runner.func.value.id == "self"
                        ):
                            # Single-source full pipeline orchestration is allowed when
                            # validate_and_simulate delegates to the unified runner.
                            return
                    if (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "_build_result"
                        and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == "self"
                    ):
                        by_arg: dict[str, ast.expr] = {
                            str(kw.arg): kw.value for kw in call.keywords if kw.arg is not None
                        }
                        required_kw = {
                            "status",
                            "decision",
                            "payload",
                            "agent_feedback",
                            "validation_session",
                            "replay_bundle",
                            "forensic_bundle",
                            "security_trace",
                            "evidence_schema_version",
                            "evidence_v2",
                        }
                        missing_kw = sorted(required_kw - set(by_arg))
                        if missing_kw:
                            failures.append(
                                "validate-and-simulate-contract: `_build_result` missing kwargs "
                                + ", ".join(f"`{k}`" for k in missing_kw)
                            )
                        af = by_arg.get("agent_feedback")
                        if not (
                            isinstance(af, ast.Call)
                            and isinstance(af.func, ast.Name)
                            and af.func.id
                            in {"_build_agent_feedback_success", "build_agent_feedback_success"}
                        ):
                            failures.append(
                                "validate-and-simulate-contract: `agent_feedback` must be built "
                                "via `build_agent_feedback_success(...)`"
                            )
                        st = by_arg.get("security_trace")
                        if not isinstance(st, ast.Name):
                            failures.append(
                                "validate-and-simulate-contract: `security_trace` must be "
                                "a normalized local variable passed into `_build_result`"
                            )
                        payload_expr = by_arg.get("payload")
                        _payload_ok = False
                        if (
                            isinstance(payload_expr, ast.Call)
                            and isinstance(payload_expr.func, ast.Name)
                            and payload_expr.func.id == "result_envelope_builder"
                        ):
                            for kw in payload_expr.keywords:
                                if kw.arg == "payload" and isinstance(kw.value, ast.Call):
                                    sp = kw.value
                                    if (
                                        isinstance(sp.func, ast.Attribute)
                                        and sp.func.attr == "_simulation_payload"
                                        and isinstance(sp.func.value, ast.Name)
                                        and sp.func.value.id == "self"
                                    ):
                                        for sk in sp.keywords:
                                            if (
                                                sk.arg == "validated"
                                                and isinstance(sk.value, ast.Constant)
                                                and sk.value.value is True
                                            ):
                                                _payload_ok = True
                                                break
                        if not _payload_ok:
                            failures.append(
                                "validate-and-simulate-contract: `payload` must be "
                                "`result_envelope_builder(payload=self._simulation_payload(..., "
                                "validated=True, ...))`"
                            )
                        return
                if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                    kv_pairs: dict[str, ast.expr] = {}
                    for k, v in zip(inner.value.keys, inner.value.values):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            kv_pairs[k.value] = v
                    keys = set(kv_pairs)
                    required = {
                        "validated",
                        "simulation_outcome",
                        "policy_decision",
                        "agent_feedback",
                        "validation_session",
                        "replay_bundle",
                        "forensic_bundle",
                        "security_trace",
                        "evidence_v2",
                        "migration_modes",
                    }
                    missing = sorted(required - keys)
                    if missing:
                        failures.append(
                            "validate-and-simulate-contract: missing return keys "
                            + ", ".join(f"`{k}`" for k in missing)
                        )
                    validated_node = kv_pairs.get("validated")
                    if not (
                        isinstance(validated_node, ast.Constant) and validated_node.value is True
                    ):
                        failures.append(
                            "validate-and-simulate-contract: `validated` must be literal `True`"
                        )
                    agent_feedback = kv_pairs.get("agent_feedback")
                    if not (
                        isinstance(agent_feedback, ast.Call)
                        and isinstance(agent_feedback.func, ast.Name)
                        and agent_feedback.func.id
                        in {"_build_agent_feedback_success", "build_agent_feedback_success"}
                    ):
                        failures.append(
                            "validate-and-simulate-contract: `agent_feedback` must be built via "
                            "`build_agent_feedback_success(...)`"
                        )
                    trace_node = kv_pairs.get("security_trace")
                    if not isinstance(trace_node, ast.Name):
                        failures.append(
                            "validate-and-simulate-contract: `security_trace` must be a "
                            "normalized local variable"
                        )
                    return
            failures.append(
                "validate-and-simulate-contract: no `_build_result` or dict return found"
            )
            return
    failures.append("validate-and-simulate-contract: function not found")


def _extract_python_blocks(doc: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"```python\s*\n(.*?)```", doc, re.DOTALL)]


def _name_from_expr(expr: ast.expr) -> Optional[str]:
    if isinstance(expr, ast.Name):
        return expr.id
    return None


def _assert_readme_broadcast_contract(*, readme: str, failures: list[str]) -> None:
    # Gate: sign_and_broadcast must consume semantic tx payload only.
    # Allowed:
    #   1) tx_payload = Lirix.extract_broadcast_fields(result)
    #   2) tx_payload from result["payload"] keys (or p = result["payload"] then p["to"], ...)
    #   3) tx_payload = result["tx_payload"]
    # Blocked:
    #   - sign_and_broadcast(result)
    #   - sign_and_broadcast(any_alias_not_whitelisted)
    for block in _extract_python_blocks(readme):
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        tx_payload_aliases: set[str] = set()
        result_aliases: set[str] = set()
        payload_aliases: set[str] = set()
        blacklisted_aliases: set[str] = set()

        def _slice_key(node: ast.Subscript) -> Optional[str]:
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                return node.slice.value
            if isinstance(node.slice, ast.Index) and isinstance(node.slice.value, ast.Constant):
                v = node.slice.value.value
                return str(v) if isinstance(v, str) else None
            return None

        def _is_result_subscript(node: ast.Subscript, alias: str, key: str) -> bool:
            if not isinstance(node.value, ast.Name) or node.value.id != alias:
                return False
            sk = _slice_key(node)
            return sk == key

        def _is_result_payload_field(node: ast.Subscript, alias: str, key: str) -> bool:
            if not isinstance(node.value, ast.Subscript):
                return False
            inner = node.value
            if not isinstance(inner.value, ast.Name) or inner.value.id != alias:
                return False
            if _slice_key(inner) != "payload":
                return False
            return _slice_key(node) == key

        def _is_payload_name_subscript(node: ast.Subscript, palias: str, key: str) -> bool:
            if not isinstance(node.value, ast.Name) or node.value.id != palias:
                return False
            return _slice_key(node) == key

        def _is_allowed_tx_payload_dict(
            *,
            node: ast.Dict,
            result_aliases: set[str],
            payload_aliases: set[str],
        ) -> bool:
            kv: dict[str, ast.expr] = {}
            for k, v in zip(node.keys, node.values):
                if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                    return False
                kv[k.value] = v
            required = {"to", "data", "value"}
            if set(kv.keys()) != required:
                return False
            to_expr, data_expr, value_expr = kv["to"], kv["data"], kv["value"]
            for pal in payload_aliases:
                if _is_payload_name_subscript(to_expr, pal, "to") and _is_payload_name_subscript(
                    data_expr, pal, "data"
                ):
                    if (
                        isinstance(value_expr, ast.Call)
                        and isinstance(value_expr.func, ast.Attribute)
                        and isinstance(value_expr.func.value, ast.Name)
                        and value_expr.func.value.id == pal
                        and value_expr.func.attr == "get"
                        and len(value_expr.args) >= 1
                        and isinstance(value_expr.args[0], ast.Constant)
                        and value_expr.args[0].value == "value"
                    ):
                        return True
                    if _is_payload_name_subscript(value_expr, pal, "value"):
                        return True
            for alias in result_aliases:
                if _is_result_payload_field(to_expr, alias, "to") and _is_result_payload_field(
                    data_expr, alias, "data"
                ):
                    if (
                        isinstance(value_expr, ast.Call)
                        and isinstance(value_expr.func, ast.Attribute)
                        and isinstance(value_expr.func.value, ast.Subscript)
                        and _is_result_subscript(value_expr.func.value, alias, "payload")
                        and value_expr.func.attr == "get"
                        and len(value_expr.args) >= 1
                        and isinstance(value_expr.args[0], ast.Constant)
                        and value_expr.args[0].value == "value"
                    ):
                        return True
                    if _is_result_payload_field(value_expr, alias, "value"):
                        return True
                if not (
                    isinstance(to_expr, ast.Subscript)
                    and _is_result_subscript(to_expr, alias, "to")
                    and isinstance(data_expr, ast.Subscript)
                    and _is_result_subscript(data_expr, alias, "data")
                ):
                    continue
                if (
                    isinstance(value_expr, ast.Call)
                    and isinstance(value_expr.func, ast.Attribute)
                    and isinstance(value_expr.func.value, ast.Name)
                    and value_expr.func.value.id == alias
                    and value_expr.func.attr == "get"
                    and len(value_expr.args) >= 1
                    and isinstance(value_expr.args[0], ast.Constant)
                    and value_expr.args[0].value == "value"
                ):
                    return True
                if isinstance(value_expr, ast.Subscript) and _is_result_subscript(
                    value_expr, alias, "value"
                ):
                    return True
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                value = node.value
                if isinstance(value, ast.Call):
                    fn = _name_from_expr(value.func)
                    attr = value.func.attr if isinstance(value.func, ast.Attribute) else None
                    if (
                        isinstance(value.func, ast.Attribute)
                        and isinstance(value.func.value, ast.Name)
                        and value.func.value.id == "Lirix"
                        and value.func.attr == "extract_broadcast_fields"
                        and value.args
                        and isinstance(value.args[0], ast.Name)
                        and value.args[0].id in result_aliases
                    ):
                        tx_payload_aliases.add(target.id)
                        continue
                    if fn in {
                        "validate_and_simulate",
                        "async_validate_and_simulate",
                    } or attr in {
                        "validate_and_simulate",
                        "async_validate_and_simulate",
                    }:
                        result_aliases.add(target.id)
                if isinstance(value, ast.Subscript):
                    base = value.value
                    if isinstance(base, ast.Name) and base.id in result_aliases:
                        sk = _slice_key(value)
                        if sk == "tx_payload":
                            tx_payload_aliases.add(target.id)
                        elif sk == "payload":
                            payload_aliases.add(target.id)
                if isinstance(value, ast.Dict):
                    if _is_allowed_tx_payload_dict(
                        node=value,
                        result_aliases=result_aliases,
                        payload_aliases=payload_aliases,
                    ):
                        tx_payload_aliases.add(target.id)
                    else:
                        blacklisted_aliases.add(target.id)
                elif isinstance(value, ast.Name) and value.id in result_aliases:
                    blacklisted_aliases.add(target.id)
        if not result_aliases:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = _name_from_expr(node.func)
                if fn != "sign_and_broadcast" or not node.args:
                    continue
                arg0 = node.args[0]
                if isinstance(arg0, ast.Name) and arg0.id in result_aliases:
                    failures.append(
                        "readme-contract: sign_and_broadcast(...) must not consume raw "
                        "validate_and_simulate result objects"
                    )
                    return
                if isinstance(arg0, ast.Name) and arg0.id in blacklisted_aliases:
                    failures.append(
                        "readme-contract: sign_and_broadcast(...) consumed non-whitelisted "
                        "aggregate object; only semantic tx_payload aliases are allowed"
                    )
                    return
                if not isinstance(arg0, ast.Name) or arg0.id not in tx_payload_aliases:
                    failures.append(
                        "readme-contract: sign_and_broadcast(...) must consume an allowed "
                        "`tx_payload` alias (`Lirix.extract_broadcast_fields(result)`, "
                        "`result['payload']` mapping, or `result['tx_payload']`)"
                    )
                    return


def main() -> int:
    failures: list[str] = []
    ci = _read(".github/workflows/ci.yml")
    tools_gates_index = _read("docs/tools_gates_index.md")
    api = _read("docs/api_reference.md")
    arch = _read("docs/architecture_control_plane.md")
    checklist = _read("docs/checklist_implementation_matrix.md")
    audit_map = _read("docs/audit_path_map.md")
    release = _read("docs/release_notes.md")
    readme = _read("README.md")
    exceptions_source = _read("lirix/core/exceptions.py")
    client_source = _read("lirix/_facade.py")

    _assert_governance_explicit_step_line_in_ci_yml(ci, failures)
    _validate_tools_gates_index_row_parity(tools_gates_index, failures)

    gated_tests = _extract_governance_gate_tests(ci)
    # Minimal anchors only: the exhaustive governance pytest list lives solely in
    # `.github/workflows/ci.yml` (`GOVERNANCE_GATE_EXPLICIT_STEP_NAME`). Every audit map row with
    # CI gate "Governance gate" must reference tests that appear in that extracted list
    # (enforced in the loop below). These paths are "must not disappear from CI YAML" probes
    # so an accidental truncation of the workflow still trips a clear failure.
    _validate_governance_explicit_list(gated_tests, failures)

    # Audit map table must reference real code/tests, and gated rows must be in the explicit gate.
    audit_rows = _extract_audit_map_rows(audit_map)
    for row in audit_rows:
        test_paths = _extract_backticked_paths(row["test_path"])
        code_paths = _extract_backticked_paths(row["code_path"])
        _require_paths_exist(test_paths, failures=failures, context="audit_path_map.test_path")
        _require_paths_exist(code_paths, failures=failures, context="audit_path_map.code_path")
        if row["ci_gate"].strip() == "Governance gate":
            for tp in test_paths:
                if tp.startswith("tests/") and gated_tests and tp not in gated_tests:
                    failures.append(f"audit_path_map: test not in governance gate `{tp}`")

    _audit_map_client_core_paths(audit_rows, failures)
    _assert_exception_inheritance_contract(
        api_doc=api,
        exceptions_source=exceptions_source,
        failures=failures,
    )
    _assert_validate_and_simulate_return_contract(client_source=client_source, failures=failures)
    _assert_readme_broadcast_contract(readme=readme, failures=failures)

    _require_all(
        release,
        "release-notes",
        ["## API Contract Delta", "additive and backward compatible"],
        failures,
    )
    _require_all(
        api,
        "api-reference",
        [
            "canonical_error_code",
            "failure_type_canonical",
            "error_codes",
            "canonical_error_codes",
            "decision_log",
            "lifecycle",
            "replay_session(bundle)",
            "Lirix.resolve_failure_protocol(context)",
            "Lirix.extract_broadcast_fields",
        ],
        failures,
    )
    _require_all(
        api,
        "api-reference-policy-rollback-doc",
        ["policy_lifecycle_and_rollback.md"],
        failures,
    )
    _require_all(
        arch,
        "architecture-control-plane",
        [
            "failure_protocol.failure_type_canonical",
            "forensic_bundle.canonical_error_codes",
            "tests/test_core/test_canonical_semantics.py",
        ],
        failures,
    )
    _require_all(
        checklist,
        "checklist-implementation-matrix",
        [
            "forensic_bundle.canonical_error_codes",
            "CI 显式 governance gate 覆盖 canonical/session/entrypoints/hook/langchain",
            "harness.py root-import-surface",
            "harness.py test-monkeypatch-convention",
        ],
        failures,
    )
    _require_all(
        readme,
        "readme",
        ["canonical_error_code", "failure_type_canonical", "canonical_reason_codes"],
        failures,
    )

    if failures:
        for msg in failures:
            print(msg)
        return 1
    return 0


def check_contract_manifest() -> int:
    return int(main())
