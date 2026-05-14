# Release Notes

This document records release-visible deltas and compatibility notes only. It is not a second SSOT for architecture or workflow governance.

**EN:** Version history and API contract deltas for Lirix releases.<br>
**中文：** 版本历史与 API 契约增量说明；契约门禁敏感锚点见 § **API Contract Delta** 及文末兼容性声明。

---

## Unreleased

- **G-008 documentation audit (closed cycle):** structured audience / consistency register at **`docs/documentation_ux_audit_register.md`** (not a line-by-line proof of every `docs/**` file).
- **G-008（中文）：** 结构化读者矩阵与一致性核对见 **`docs/documentation_ux_audit_register.md`**（非对 `docs/**` 全量逐行审阅证明）。
- **PyPI classifiers:** `Development Status` updated from **Beta** to **`Production/Stable`** to align PyPI metadata with the **2.x** stability narrative (README § Stability cross-reference). Semver and `docs/migration_legacy_to_v2.md` still govern breaking releases.
- **CV rubric v2:** `docs/cv_rubric.yaml` `version` bumped after **`ci_alignment`** automated sub-score re-weighting (cache / diff hygiene only; scoring script unchanged). See `docs/architecture_evolution_action_list.md` top note.
- **CV rubric v2（中文）：** 同上；`ci_alignment` 子项分值重分配后递增 `version`，便于外部缓存与 diff 识别语义批次，详见 **`docs/architecture_evolution_action_list.md`** 顶栏说明。

- **Optional SBOM / Anvil E2E (procurement / sign-off):** optional workflows are indexed in **`docs/ci_gate_matrix.md`** — see **§ Optional SBOM / Anvil E2E — procurement and release sign-off (manual)** for how to run them in GitHub Actions and attach artifacts to vendor or release checklists (no external CD SaaS).
- **可选 SBOM / Anvil E2E（采购与发布签核）：** 与上条英文并列；可选工作流索引见 **`docs/ci_gate_matrix.md`**，手动采购与签核步骤见同文件 **§ Optional SBOM / Anvil E2E — procurement and release sign-off (manual)**（无外部 CD SaaS）。

- **Root `__all__` shrink (breaking for imports that relied on root re-exports):** the package root now exports only `Lirix`, `LirixConfig`, `LirixSecurityException`, `replay_session`, `verify_replay_bundle`, `atomic_multicall`, `register_hook`, `resolve_failure_protocol`, and `build_for_chain_profile`. Use `lirix.core`, `lirix.layers`, and `lirix.audit.logger` for everything else. See **`docs/migration_legacy_to_v2.md`** (**§ Root export policy**); future export changes will cross-reference that section in each release entry.
- **`chain_validate` policy:** documented **only** as a **`bool` view** on the same recorded path as **`validate_only`** (not a parallel semantics fork). Prefer **`validate_only`** / full pipeline responses when you need evidence payloads.
- **Single-stack convergence started:** defaults now target `rpc_evidence_mode=v2_only` and `policy_lifecycle_mode=digest_verified`; strict mode rejects non-target stack modes.
  - **Coercion-only migration aliases:** legacy labels are accepted **only** as input compatibility shims and are **immediately coerced** to the single-stack runtime modes during config normalization:
    - `rpc_evidence_mode=legacy|v2_dual` → `v2_only`
    - `policy_lifecycle_mode=legacy|signed_only` → `digest_verified`
  - **Freeze policy (release discipline):** docs/examples/tests must **not** add new usage of legacy alias inputs (`legacy`, `v2_dual`, `signed_only`). New callsites must use the single-stack target modes.
  - **Next-major hard removal window:** alias-input acceptance is scheduled for removal in the **next major release** (see `docs/migration_legacy_to_v2.md` for the authoritative migration timeline). Until then, alias inputs emit `DeprecationWarning` and are coerced.

### Contract and Runtime Boundary

- Unified Python support boundary to `3.9–3.14`.
- Runtime import check now enforces `3.9 <= Python < 3.15`.
- Removed `3.8` classifier metadata from package definition.

### Security Evidence Model

- Introduced `SecurityTrace` and `ExecutionEvidence`.
- `validate_and_simulate` and `async_validate_and_simulate` now return `security_trace`.
- Added correlation id, payload digest summary, and per-layer step evidence.

### Hook Contract Hardening

- Standardized isolated hook result schema with:
  - `schema_version`
  - `error_code`
  - `error_type`
  - `retryable`
- Preserved compatibility with existing `ok`, `hook_point`, `error`, and `result`.

### Policy Metadata

- Added `policy_id`, `policy_version`, and `environment` to `ShadowPolicySchema`.
- Added `decision_report` for explicit policy decision evidence embedding.

### API Contract Delta

- Added `agent_feedback.reason_code` fixed taxonomy (e.g. `LIRIX_REASON_OK`, `LIRIX_REASON_TIMEOUT`).
- Added `SimulationOutcome` replay fields:
  - `assumptions`
  - `state_delta_digest`
  - `policy_match_ids`
- Added `RPCDisagreementReport.taxonomy` execution guidance fields:
  - `severity`
  - `remediation`
- Added session-level local replay and forensic outputs:
  - `replay_bundle`
  - `forensic_bundle`
- Added multi-chain profile registries:
  - `protocol_registry`
  - `address_registry`
  - `simulation_backend_profile`
- Added policy rollback behavior in bundle resolution (`rollback_to` with `rollback_applied` report flag).
- Added top-level failure protocol resolver: `Lirix.resolve_failure_protocol(...)`.
- Added replay closure anchor: `replay_bundle.registry_closure_digest`.
- Added forensic alignment field: `forensic_bundle.agent_reason_codes`.
- Added LangChain guided mode input: `mode=validate_only|validate_and_simulate`.
- Added governance canonicalization utility: `lirix.core.canonicalize_error_code`.
- Expanded legacy `LRX_* -> LIRIX_ERR_*` canonicalization coverage for runtime-emitted legacy codes.
- Added strict canonical reason validation mode: `canonicalize_reason_code(..., strict=True)`.
- Added explicit raw taxonomy fields:
  - `RPCDisagreementReport.taxonomy.*.raw_reason_code`
  - `forensic_bundle.raw_error_codes`
- Added replay/session hardening checks:
  - runtime session status/verdict validation
  - replay metadata consistency guard across session traces
  - replay proof validation for `registry_version` and `registry_source`
- Added public export contract tests for `lirix`, `lirix.core`, and `lirix.layers`.
- Added static helper `Lirix.extract_broadcast_fields(result)`: read-only view over `result["payload"]` returning `to` / `data` / `value` for signing/broadcast prep.
- Packaged `lirix._client_core` as a **package** (replacing the historical single-file `_client_core.py`); monkeypatch entrypoints remain `lirix._client_core.<symbol>` per `docs/api_reference.md`.
- **Fail-closed broadcast extract:** calling `Lirix.extract_broadcast_fields(result)` when `decision` and `status` are not both `"approved"` raises `LirixSecurityException` with `context["reason"] == "broadcast_extract_requires_dual_approved"` and canonical code `LIRIX_ERR_BROADCAST_PAYLOAD_INVARIANT`. When both are `"approved"`, `to` / `data` under `result["payload"]` must each be a **non-empty string** (type `str`, not empty/whitespace) with valid hex-shaped `data`; otherwise `LirixSecurityException` is raised with `context["reason"] == "approved_broadcast_fields_invariant"` and the same canonical code.
- **Broadcast extract summary:** `Lirix.extract_broadcast_fields(result)` is the supported one-liner for prepared broadcast payloads after the dual-approved gate; it enforces fail-closed `to`/`data` validation on that path only.
- **LangChain / AutoGen success JSON:** serialized success payloads now include additive `tx_payload` (JSON object mirroring `Lirix.extract_broadcast_fields(result)`) alongside existing keys.

All changes are additive and backward compatible with existing payload keys.

- `atomic_multicall` return mapping may include audit fields aligned with `validate_only`:
  `replay_bundle`, `validation_session`, `forensic_bundle`, `security_trace`,
  `evidence_schema_version`, `evidence_v2`, `migration_modes`.
- `chain_validate`: uses the same recorded L1–L3 path as `validate_only` (success returns `True`). **Authoritative policy:** see **Unreleased** above — **`chain_validate` policy**.
- `policy_lifecycle_mode` adds `digest_verified`; `signed_only` remains as a deprecated alias.
- `PolicyVersion` adds `integrity_digest` (preferred over legacy `signature` for the same digest semantics).
- `migration_modes` on pipeline results includes `policy_lifecycle_mode_effective`.
- `l1_l3_ok` semantics (four entrypoints, full-pipeline hook order vs gate): authoritative text is **[Session gate semantics (l1_l3_ok)](audit_path_map.md#session-gate-semantics-l1_l3_ok)** in `docs/audit_path_map.md`.
