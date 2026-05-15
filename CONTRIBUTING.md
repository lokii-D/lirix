# 🛠️ Contributing to Lirix

**EN:** Contribution workflow, quality bar, and the single harness router (`tools/harness.py`) for policy gates. Bilingual Markdown conventions: [`docs/documentation_styleguide.md`](docs/documentation_styleguide.md) (SSOT).

Lirix welcomes contributors who respect deterministic systems, security boundaries, and production-grade engineering discipline. We are friendly, but we are exacting: if a change weakens the trust model, slips on quality, or introduces ambiguity, it will not be merged.

## 🧭 At a glance

- **Use one policy door** — every gate routes through `python tools/harness.py <subcommand>`.
- **Meet the quality bar** — tests, types, lint, and formatting must all pass.
- **Protect the boundary** — zero-key, zero-telemetry, and zero-trust are non-negotiable.
- **Keep docs in sync** — release-facing docs must match the code and versioned contract.

## The 1000% 极客标准

Every pull request must satisfy **all** of the following before review can proceed:

- `pytest` passes with `[tool.coverage.report].fail_under = 100` on `lirix/` and no regression on touched surfaces.
- `mypy --strict lirix` is clean — no `Any` escape hatches for new public contracts.
- `ruff check .` reports zero violations; `python tools/harness.py format-check` (Black **24.10.0** from `.[dev]`, `--check --quiet`) is clean — do not trust a globally installed newer Black against this repo (formatter rules differ → false “would reformat”).
- The Zero-Key, Zero-Telemetry, Zero-Trust boundary stays intact.
- Behavior changes ship with tests that prove the new path and guard the old one.
- PRs that break `lirix init` idempotency, including `.env` hygiene, are rejected.
- PRs that weaken L4 concurrency or retry semantics under `429` or timeout paths are rejected.
- Release-facing docs stay aligned with `pyproject.toml` `[project].version` and `docs/api_reference.md`.

Missing any item above is an auto-reject until fixed. For the command surface itself, prefer the tables below instead of expanding prose with new one-off command lists.

## Harness router

All repository policy gates are invoked through one front door:

```bash
python tools/harness.py <subcommand>
```

The subcommand map is `COMMANDS` in `tools/harness.py`; implementations live in `tools/validators.py`. `python tools/harness.py contract-manifest` wraps `tools/contract_manifest_gate.py` and enforces the docs / audit-table / README broadcast contract. Release-preflight roll-up (import-topology drift + documented git hazards): `python tools/harness.py preflight-remediation-status` — playbook `docs/preflight_remediation_executor_handoff.md`.

### Fast Required parity for a typical PR:

| Area | Canonical command(s) | Notes |
| --- | --- | --- |
| Authoritative Python | `python3.12` (see repo `.python-version`) | CI **Fast Required** / **coverage** use **3.12**; run the same before claiming merge or release parity. |
| Formatting / lint / types | `python -m black --check --quiet .`, `python -m ruff check .`, `python -m mypy --strict lirix` | Prefer `python tools/harness.py format-check` (pins **Black 24.10.0** via `pip install -e ".[dev]"`; never substitute system Black 26.x for gate parity). |
| Tests | `pytest`, `pytest -o addopts= tests --pyargs lirix`, targeted regression suites | Use the narrowest command that proves the change. A **full default** `pytest` may show **four** expected skips (perf baseline env + Anvil E2E RPC); see `docs/ci_gate_matrix.md` § **Full default collection — expected `pytest` skips**. |
| Governance / drift | `python tools/harness.py preflight-remediation-status`, `python tools/harness.py contract-manifest` | The pair covers topology drift, known hazard paths, and doc / audit parity. |
| Docs / import surface | `python tools/harness.py audit-internal-link`, `python tools/harness.py doc-preamble-hygiene`, `python tools/harness.py no-internal-imports`, `python tools/harness.py root-import-surface` | Run when touching docs or public import surfaces. |
| Test conventions | `python tools/harness.py test-monkeypatch-convention --strict` | Use when patching or refactoring tests. |

Add `--enforce` to `doc-preamble-hygiene` locally if you need CI-warn paths to fail closed. Optional anvil / Foundry steps apply when you touch L5 integration surfaces — see `docs/contributing_local_tests.md`.

Full subcommand inventory and exit codes: `docs/tools_gates_index.md`. Workflow wiring: `docs/ci_gate_matrix.md`. Periodic documentation UX / audience alignment checklist: `docs/documentation_ux_audit_register.md`.

## Public surface & architecture truth

Keep these aligned with `docs/audit_path_map.md`, `docs/migration_legacy_to_v2.md`, and `docs/api_reference.md`:

- **Single orchestrated DAG:** `Lirix` in `lirix/_facade.py` delegates to `LirixPipelineOrchestrator` — do not fork parallel client stacks for the same contracts.
- **Frozen root exports:** `lirix.__all__` matches `tests/test_core/test_public_exports_contract.py` — no third “shadow” export list in prose-only docs.
- **Monkeypatch discipline:** `python tools/harness.py test-monkeypatch-convention --strict` plus `docs/api_reference.md` — prefer `lirix._facade.Lirix`, `lirix._client_core.<pipeline symbols>`, `lirix.core.session.*`, `lirix.layers.*`, `lirix.integrations.*`; never patch the bare `lirix` package object.
- **`chain_validate`:** bool sugar on the same path as `validate_only` — use full entrypoints when you need evidence payloads.
- **Audit table edits:** changing `docs/audit_path_map.md` § Core Assertions Map requires `python tools/harness.py contract-manifest` locally.

## What we do not merge

## PR lifecycle

1. Fork → narrow feature branch.
2. Implement and test locally with the gates above.
3. Open PR only when the branch is clean and reproducible.
4. Release and sign-off PRs: `docs/release_pr_checklist.md` plus `audit_artifacts/release_signoff/README.md`.

## 🚫 What we do not merge

- Private-key handling inside the library
- Hidden telemetry
- Non-deterministic safety checks
- Typing or lint shortcuts to greenwash CI
- Security boundary relaxations without reviewed design
- `lirix init` path confinement or `.env` hygiene regressions
- L4 resilience regressions on `429`, timeout, or concurrent retry paths

## Dependency security

- Run `pip-audit` on the release virtualenv after `pip install -e ".[dev]"`.
- Enable Dependabot or equivalent. Merging bumps still requires the normal CI bar.
- Optional SBOM: `docs/sbom_optional.md`, `.github/workflows/sbom-optional.yml`.

---

## 中文导读（贡献者摘要）

**中文：** 贡献流程与质量标准；权威体例见 [`docs/documentation_styleguide.md`](docs/documentation_styleguide.md)。

- **单点路由门禁：** 所有策略门闸统一走 **`python tools/harness.py <subcommand>`**。映射在 **`tools/harness.py` → `tools/validators.py`**。`contract-manifest` 负责文档、审计表与 README 广播契约的校验；发布前聚合门 **`preflight-remediation-status`**（导入拓扑 + 工作区一致性）见 **`docs/preflight_remediation_executor_handoff.md`**。
- **质量门槛：** `pytest`（`lirix/` 行覆盖率 100%）、`mypy --strict lirix`、`ruff`、`black --check` 全绿；不得削弱零密钥 / 零遥测 / 零信任边界；行为变更必须带测试双锁。
- **架构事实：** 对外 `Lirix` 在 `lirix/_facade.py`，编排内核在 `lirix/core/orchestrator.py`；不要再造第二套并行客户端栈。根导出以 `tests/test_core/test_public_exports_contract.py` 为冻结真相源。
- **Monkeypatch 纪律：** 见 `docs/api_reference.md` 和 `python tools/harness.py test-monkeypatch-convention --strict`。
- **审计表：** 修改 `docs/audit_path_map.md` 的 Core Assertions Map 后，必须本地跑 `python tools/harness.py contract-manifest`。
- **不合并项：** 库内触钥、隐蔽遥测、非确定性安检、为提速放松校验等。
- **依赖安全：** 发布前建议 `pip-audit` / Dependabot；可选 SBOM 见 `docs/sbom_optional.md`。

> **中文硬核版：** 我们很友好，但我们不讲情面——`pytest` 覆盖率必须 100%，`mypy --strict` 不接受任何投机性 `Any` 漏洞，`ruff` 必须全绿；谁要是想靠放水把 CI 染绿，门禁会直接把它挡回去。
