# Migration: Legacy to V2


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

Single audit entrypoint (architecture → code → tests → evidence → CI): **[`docs/audit_path_map.md`](audit_path_map.md)**.

## 🛡️ Compatibility

Lirix runtime is single-stack (`rpc_evidence_mode=v2_only`, `policy_lifecycle_mode=digest_verified`).
Legacy labels are accepted only as input aliases and are normalized immediately during config loading.

## LirixGuard `last_trace` (legacy helper)

[`LirixGuard`](../lirix/legacy-guard-removed.py) sets `last_trace` after `parse` / `async_parse`.
Treat **`raw_payload`**, **`latency`**, **`pipeline_result_keys`**, and optionally **`security_trace`**
as the only documented stable fields — not a stable ABI for older trace objects.

## Root export policy (`lirix.__all__` roadmap)

**Authoritative root `__all__`:** [`tests/test_core/test_public_exports_contract.py`](../tests/test_core/test_public_exports_contract.py) **`test_root_package_exports_contract`** (membership frozen, no duplicates; order is non-semantic).

**As of v2.0.3:** the root package re-exports **`HookManager`**, **`RPCManager`**, **`SandboxSimulator`**, **`ProxyPiercer`**, and **`SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR`** alongside the evidence-oriented **`Lirix`** entrypoints. Prefer **`from lirix import …`** in README / quickstart / examples for those symbols. Still import from subpackages when you need symbols not listed on the root:

- **Layers** (`ShadowAuditor`, `ShadowPolicySchema`, `AbiLRUCache`, …): `from lirix.layers import …`
- **Hooks / multicall / other exceptions** (e.g. `MulticallEncoder`): `from lirix.core import …` or `from lirix.core.exceptions import …`
- **`AuditLogger`**: `from lirix.audit.logger import AuditLogger`

**Minor B:** in README / quickstart / examples, default to **`from lirix import …`** for the root-re-exported pipeline symbols above; use **`from lirix.layers import …`** for advanced layer-only types.

**Scheduled removals (version-gated; do not rely on soft dates in prose alone)** — track in **release notes** per version; see also **§ Root export policy** there:

- **`Guardian`** alias (`lirix._client_core`), **`sessionized_*`** methods: remove after the published deprecation window.
- **`lirix.core.guard`**: Lirix **2.0** — remove shim or replace with hard `ImportError` pointing at `lirix.legacy`.
- **`chain_validate`**: **policy locked** — documented **only** as a **`bool` view** of the same recorded path as **`validate_only`** (success ⇒ `True`). For evidence and replay, use **`validate_only`** / full pipeline returns; do **not** treat `chain_validate` as a second semantic path.

## Legacy surface inventory (read-only; semver-preserving)

| Surface | Role | Documented import path | Invariants / tests |
| --- | --- | --- | --- |
| `lirix.shield` | legacy namespace; **not** stability-bound with `lirix.layers` | Prefer `from lirix.layers import …` for new code | `docs/audit_path_map.md` Scope; contract tests treat shield as legacy-only narrative |
| `lirix.legacy` (e.g. `LirixGuard`) | compatibility shims delegating to `lirix._client_core` | `from lirix.legacy import …` during deprecation window | `tests/test_core/test_entrypoint_symbol_binding_contract.py`, rows in **`docs/audit_path_map.md`** Optional follow-ups |
| `lirix.core.guard` | deprecated re-export (`DeprecationWarning`) until Lirix 2.0 | migrate to `lirix.legacy` / `Lirix` | same binding contract tests + audit map note |

No additional runtime removals are implied here — this inventory exists to prevent silent import drift while staying **additive-only** for semver.

### Contributor grep (external reference audit)

When changing pipeline semantics, scan for **legacy import surfaces** (read-only audit; do not bulk-delete without semver plan):

```bash
rg -n "from lirix\\.shield|import lirix\\.shield" --glob '!tdsc/**' --glob '!mantle_TT/**'
rg -n "from lirix\\.legacy|import lirix\\.legacy" --glob '!tdsc/**' --glob '!mantle_TT/**'
rg -n "lirix\\.core\\.guard|from lirix\\.core import.*guard" --glob '!tdsc/**' --glob '!mantle_TT/**'
```

Treat hits in **`examples/`**, **`docs/`**, and **`tests/`** as migration debt to schedule; hits in **`lirix/`** core paths should follow **`docs/audit_path_map.md`** and release-note policy.

## `lirix.shield` / `lirix.shield.simulator` (non-stable public surface)

[`lirix/shield/simulator.py`](../lirix/shield/simulator.py) is a **legacy namespace**: **not** guaranteed to track the main DAG or `lirix.layers` L5 behavior. **Do not** rely on it as a stable public SDK surface for new products — use **`lirix.layers`** (`SandboxSimulator`, etc.). Relocation to a private test-support package or removal requires an explicit ADR and bulk import updates.

## Scheduled removals — maintainer execution phases

Concrete phases (coordinate semver / PyPI with the release PR that lands each phase):

| Phase | Target | Steps |
|-------|--------|--------|
| 1 | **`Guardian`** (`lirix._client_core`) | Add or tighten `DeprecationWarning` on access; grep README/docs/tests; remove alias in a numbered release; keep README historical index one line if needed. |
| 2 | **`sessionized_*`** | Remove methods after deprecation window; drop targeted `filterwarnings` in `pyproject.toml`; grep docs/tests. |
| 3 | **`lirix.core.guard`** | Lirix **2.0**: replace shim with `ImportError` + message pointing to `from lirix.legacy import …`, or delete module; update **`tests/test_core/test_entrypoint_symbol_binding_contract.py`**. |
| 4 | **`chain_validate`** | Only if policy changes from current **bool-sugar** narrative (would require ADR + deprecation cycle first). |

## Single-stack convergence timeline

Convergence target (single-stack runtime):

- `rpc_evidence_mode`: `v2_only` (legacy/v2_dual runtime branches retired)
- `policy_lifecycle_mode`: `digest_verified` (legacy runtime branch retired)

Execution schedule:

1. **Freeze new legacy usage (now)**: docs/examples/tests must not add new legacy/v2_dual/signed_only usage.
2. **Compatibility window (current)**: legacy input labels are accepted only as migration aliases and are coerced to single-stack runtime modes.
3. **Hard removal (next major)**: remove legacy migration aliases from input validation entirely.

## Legacy convergence route (operational checklist)

Use this route to retire legacy inputs without changing public entrypoints:

1. Set `hook_contract_mode="shadow"` in production-like environments and verify hook contract warnings are zero.
2. Keep `policy_lifecycle_mode="digest_verified"` and `rpc_evidence_mode="v2_only"` as explicit config values (do not rely on alias coercion).
3. Treat any alias-input warning (`legacy` / `signed_only` / `v2_dual`) as release-blocking migration debt.
4. Before the next major, remove alias inputs from docs, examples, and deployment manifests.

Coercion-only definition (what “compatibility window” means):

- Alias inputs are accepted **only** to unblock downstream migrations.
- They do **not** enable legacy runtime behavior; they are **immediately coerced** during config normalization:
  - `rpc_evidence_mode=legacy|v2_dual` → `v2_only`
  - `policy_lifecycle_mode=legacy|signed_only` → `digest_verified`
- Every alias-input use emits `DeprecationWarning`. Downstream integrations must treat warnings as “migration debt” and remove alias inputs before the next major.

## Migration state machine

- **Removed**: runtime behavior for `rpc_evidence_mode=legacy|v2_dual`, `policy_lifecycle_mode=legacy`.
- **Migrating**: input aliases (`legacy`, `v2_dual`, `signed_only`) are coercion-only compatibility shims.
- **Pending removal**: alias input acceptance in the next major version.

## Recommended rollout

1. Enable `hook_contract_mode=warn` or `shadow` to observe contract compliance.
2. Keep `rpc_evidence_mode=v2_only` and migrate any consumer still parsing legacy-only fields.
3. Keep `policy_lifecycle_mode=digest_verified` and migrate away from legacy aliases.
4. Consume `failure_protocol` and `get_repair_instruction` for agent retry flows.

## Canonical semantics alongside legacy `error_code`

Lirix keeps legacy `error_code` values for compatibility while exposing canonical fields in the same runtime payload:

- `exception.canonical_error_code` (governance identity)
- `replay_bundle` closure anchors (`config_fingerprint`, `registry_closure_digest`, `replay_proof.*`)
- L4 failure contexts may carry:
  - `raw_error_code`
  - `canonical_error_code`

Downstream guidance:

- keep using legacy `error_code` if you must
- prefer `canonical_error_code` for automation, replay closure, and governance logic

## New helper APIs

- `Lirix.build_safe_payload(...)`
- `Lirix.get_agent_resolution(response)`
- `Lirix.get_repair_instruction(response)`

## Broadcast fields (`to` / `data` / `value`) on pipeline envelopes

Older snippets sometimes read **`result["to"]` / `result["data"]`** from the **top level** of a `validate_and_simulate` / `async_validate_and_simulate` return. The canonical envelope places broadcast targets under **`result["payload"]`** (mirrored alongside `simulation_ok` / `simulation_outcome` via `ResultBuilder.build_base_result`).

**Migration:** use **`Lirix.extract_broadcast_fields(result)`** (read-only over `result["payload"]`) or explicitly **`p = result["payload"]`** then `p["to"]` / `p["data"]` / `p.get("value", 0)` — do not rely on legacy top-level `to`/`data` keys for new code. See **`docs/api_reference.md`** (broadcast section) and **`tests/test_core/test_readme_envelope_contract.py`** for the supported contract.

## Audit checklist (recommended)

When you migrate downstream consumers, validate these joins and closures remain stable:

- join by `security_trace.correlation_id`
- verify `replay_bundle.registry_closure_digest` is present when replay bundles are emitted
- ensure downstream parsers tolerate additive fields while treating alias-input usage as migration debt

## Mode dependency notes (strict governance)

- `hook_contract_mode=enforce` requires `rpc_evidence_mode` other than `legacy` (`v2_dual` or `v2_only`).
- In `strict_mode`, governance overlap guards fail-closed:
  - `blacklisted_addresses` must not overlap with `whitelisted_addresses`
  - `blacklisted_addresses` must not overlap with `allowed_to_addresses`
