---
title: Preflight remediation — executor handoff (harness SSOT)
purpose: Single canonical brief for agents/humans to locate, fix, verify, and report audit findings tied to `preflight-remediation-status`
audience: Executor agent (implementation) → Auditor agent (re-review)
---

# Preflight remediation — executor handoff

This document is the **authoritative human playbook** paired with **`tools/preflight_remediation_contract.json`** (machine-readable rule ids). The runnable roll-up gate is:

```bash
python tools/harness.py preflight-remediation-status
```

It **must** exit `0` before a release branch is treated as CI-clean for the issues catalogued below. CI **Fast Required** and **Governance Lane** invoke this gate **before** `pip install -e ".[dev]"` (see `docs/ci_gate_matrix.md`). The JSON contract holds the structured rule ids; this playbook explains intent, verification order, and recovery steps. If you change a rule id, hazard path, or check ordering, update this file and the JSON contract in the same PR.

**Boundary rule:** this playbook is for human execution and recovery only; `tools/preflight_remediation_contract.json` is the machine-readable SSOT for rule ids, and `tools/validators.py` / `tools/harness.py` are the execution gates. Do not duplicate full rule catalogs here unless the contract or gate semantics change.

---

## 0. Executive summary for the executor

| Priority | Rule id | One-line verdict |
| --- | --- | --- |
| P0 | **R-001** | Committed `docs/lirix_import_topology.md` must match `tools/gen_lirix_import_graph.py` output (`--check`). |
| P1 | **R-002** | No tracked path in the hazard list may show git porcelain **` D`** (worktree deleted, not staged). |
| P2 | **R-003** | Process: any `lirix/**` import-edge change requires regenerating the topology doc in the **same** merge unit. |
| P3 | **R-004** | Optional policy: governance-only gates vs PR lane — documented trade-off, not an automatic defect. |
| Info | **R-005** | Local `test-coverage-required` needs `.[dev]` (pytest-cov); CI already installs dev extras first. |

**Superseded CLI note:** `python tools/harness.py import-topology` remains available and performs **only** R-001. CI now prefers **`preflight-remediation-status`** (R-001 + R-002).

---

## 1. Problem → localization → verification (per rule)

### R-001 — Import topology drift (P0 / CI hard fail)

**Problem statement**
`docs/lirix_import_topology.md` is a **generated** architecture artifact. When `lirix/**/*.py` gains, removes, or rewires **in-package** imports (`lirix` → `lirix`), the committed markdown must be regenerated. Hand-edits or stale commits cause **`import-topology-check`** to fail.

**Precise localization**

- Generator / checker: `tools/gen_lirix_import_graph.py` (`--check` compares bytes to disk).
- Output artifact: `docs/lirix_import_topology.md`.
- Harness wiring: `tools/validators.py` → `check_import_topology` → subprocess `--check`.
- Roll-up: `check_preflight_remediation_status` calls `check_import_topology` first.

**Symptoms**

- stderr contains: `import-topology-check: docs/lirix_import_topology.md is stale or hand-edited` or `preflight-remediation-status: FAIL rule R-001`.

**Verification (executor runs in order)**

1. `python tools/gen_lirix_import_graph.py --check`
2. `python tools/harness.py import-topology`
3. `python tools/harness.py preflight-remediation-status`

**Remediation architecture**

1. **Regenerate** (never patch the table by hand except in emergencies — then immediately normalize via generator):

   ```bash
   python tools/gen_lirix_import_graph.py
   ```

2. **Inspect** diff — expect only legitimate edge rows / per-module rows changing with your import edits.

3. **Stage** the markdown:

   ```bash
   git add docs/lirix_import_topology.md
   ```

4. **Re-verify** all three commands in the verification list.

**Regression / proof tests**

- `python tools/harness.py contract-manifest` (row parity + doc anchors).
- `python -m pytest -q tests/test_tools/test_preflight_remediation_status_gate.py`
- Full suite if you touched imports broadly: `python -m pytest -q`

---

### R-002 — Git index vs worktree desync on known hazard paths (P1)

**Problem statement**
A file remains **tracked** in the git index, but was **deleted on disk** without staging the deletion. Local scripts that assume `git ls-files` ⊆ filesystem, and human reviewers, see inconsistent state. Porcelain code **` D`** (space in column 1, `D` in column 2) means: *not staged for commit*, *deleted in work tree*.

**Precise localization**

- Policy encoded in: `tools/validators.py` → `check_preflight_remediation_status` (tuple `hazards`).
- Current hazard path: `tests/test_core/test_session_agent_timeline_order_happy_path.py` (successor to historical `tests/test_core/test_session_workflow_strict_happy_path.py`; R-002 still catches ` D` if this tracked file is deleted without staging).

**Verification**

```bash
git status --porcelain=v1 -uno -- tests/test_core/test_session_agent_timeline_order_happy_path.py
```

**Remediation architecture (choose one intent)**

| Intent | Command(s) | When |
| --- | --- | --- |
| **Record deletion** | `git add -u -- tests/test_core/test_session_agent_timeline_order_happy_path.py` | Test removed by design; ensure governance paths updated if needed. |
| **Restore file** | `git restore --source=HEAD -- tests/test_core/test_session_agent_timeline_order_happy_path.py` | Deletion was accidental. |

Then:

```bash
python tools/harness.py preflight-remediation-status
```

**Acceptance**

- No line from `git status --porcelain=v1 -uno -- <path>` begins with ` D` for any path in the `hazards` tuple inside `validators.py`.

**Regression / proof tests**

- `python tools/harness.py preflight-remediation-status`
- `python -m pytest -q`

---

### R-003 — Process coupling (P2)

**Problem statement**
Engineers merge `lirix/` refactors without regenerating `docs/lirix_import_topology.md`, re-triggering R-001.

**Remediation architecture**

- Add to PR template / internal checklist: *If PR touches `lirix/**/*.py` imports, run `python tools/gen_lirix_import_graph.py --check` before push.*
- Optional: pre-commit hook invoking `--check` (fast, stdlib AST only).

---

### R-004 — Lane duplication policy (P3 / informational)

**Problem statement**
Some harness subcommands run on **Governance Lane** but not on **PR Fast Required** (e.g. `failure-surface-triage`, `legacy-sunset`, `phase-exit-checklists`, `branch-protection-drift`).

**Localization**
`docs/ci_gate_matrix.md` § *Governance vs `ci.yml` overlap*.

**Remediation architecture**
Only if product policy demands **single-lane full duplication**: extend `.github/workflows/ci.yml` and update `docs/ci_gate_matrix.md` + `docs/branch_protection_required_checks.md` in the same PR. Otherwise: **no code change** — document awareness.

---

### R-005 — Local coverage gate without dev extras (info)

**Problem statement**
`python tools/harness.py test-coverage-required` invokes `pytest` with `--cov=...`. Without `pytest-cov`, pytest errors on unknown arguments.

**Remediation**

```bash
python -m pip install -e ".[dev]"
python tools/harness.py test-coverage-required
```

CI path: `lirix-ci-setup` with `with-dev-install: true` on coverage job — already satisfies this.

---

## 2. Modification suggestion architecture (how fixes compose)

```text
                    ┌──────────────────────────────┐
                    │ preflight-remediation-status │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
     check_import_topology   git porcelain scan   (future rules)
     (R-001)                  (R-002)
              │                    │
              ▼                    ▼
     gen_lirix_import_graph    hazard path tuple
        .py --check            in validators.py
```

**Adding a new audited path (extend R-002)**
Edit `tools/validators.py` — append to `hazards` in `check_preflight_remediation_status`, mirror the same path under `rules[].localization.known_hazard_paths` in `tools/preflight_remediation_contract.json`, and document in this file §1.2.

---

## 3. Concrete file / workflow touch list (expected executor diff)

When fixing the audited snapshot that motivated this harness:

| Area | Likely files |
| --- | --- |
| Topology | `docs/lirix_import_topology.md` (regenerated) |
| Test lifecycle | `tests/test_core/test_session_agent_timeline_order_happy_path.py` (delete + stage, or restore); historically `test_session_workflow_strict_happy_path.py` |
| Governance pytest SSOT | `tools/validators.py` (`GOVERNANCE_EXPLICIT_PYTEST_PATHS` if test inventory shifts) |
| CI / docs parity | `.github/workflows/ci.yml`, `.github/workflows/governance-lane.yml`, `docs/ci_gate_matrix.md`, `docs/tools_gates_index.md`, `docs/release_final_multiscan_harness_r3.md` |

---

## 4. Mandatory verification matrix (post-fix)

| Step | Command | Expected |
| --- | --- | --- |
| 1 | `python tools/harness.py hygiene` | exit 0 |
| 2 | `python tools/harness.py check-exclusions` | exit 0 |
| 3 | `python tools/harness.py preflight-remediation-status` | exit 0 |
| 4 | `python tools/harness.py lint && python tools/harness.py format-check && python tools/harness.py typecheck` | all exit 0 |
| 5 | `python tools/harness.py contract-manifest` | exit 0 |
| 6 | `python -m pytest -q` | all pass; skips only env-gated documented cases |
| 7 (non-PR / release) | `python tools/harness.py test-coverage-required` | exit 0 after `.[dev]` install |

---

## 5. Executor → auditor **return report** (paste verbatim after work)

Executor: fill every bracketed field. Auditor: reject incomplete reports.

```markdown
## Lirix preflight remediation — executor return report

### Metadata
- Date (UTC): [YYYY-MM-DDThh:mmZ]
- Commit SHA (full): [40-hex]
- Branch: [name]
- Executor: [agent id / human]

### Rule status matrix
| Rule | Status (PASS/FAIL/N/A) | Notes |
| --- | --- | --- |
| R-001 | | |
| R-002 | | |
| R-003 | | |
| R-004 | | |
| R-005 | | |

### Commands executed (ordered, copy-pasteable block)
```
[paste shell history or a single script block]
```

### Key stdout / stderr excerpts
```
[preflight-remediation-status tail]
[pytest summary line]
```

### Files changed (high level)
- [list paths]

### Unified diff stat
```
[paste output of: git diff --stat <base>...HEAD]
```

### Test evidence
- `python -m pytest -q` last line: [e.g. `1006 passed, 4 skipped in …`]
- `python tools/harness.py test-coverage-required`: [PASS/SKIPPED-with-reason / N/A]

### Risk / rollback
- [what could regress + how to revert]

### Auditor checklist (executor self-certification)
- [ ] `preflight-remediation-status` exit 0 on clean tree
- [ ] No unintended tracked artifacts under `cache/`, `__pycache__/`, `.venv/` (hygiene)
- [ ] `docs/lirix_import_topology.md` only from generator if touched
- [ ] Governance explicit list still matches intentional coverage if tests renamed

### Blockers remaining for auditor
- [none | list]
```

---

## 6. Auditor re-review procedure (strict)

1. Fetch executor branch at reported SHA.
2. Run §4 matrix in a clean worktree (or CI replay).
3. Spot-check `git show` for topology file — confirm no manual-only table edits (diff should align with import graph semantics).
4. If all green, mark audit round **CLOSED** for R-001/R-002; file follow-ups for R-003/R-004 only if policy changed.

---

## 7. References (read-only context)

- `docs/ci_gate_matrix.md` — workflow step parity.
- `docs/tools_gates_index.md` — harness subcommand catalog.
- `docs/release_final_multiscan_harness_r3.md` — multiscan grading rubric (G3 updated for preflight).
- `tools/preflight_remediation_contract.json` — structured ids for automation.
