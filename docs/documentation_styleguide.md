# Documentation styleguide（文档体例与清单）

**EN:** Single source for bilingual Markdown structure, fixed terminology, and a classified inventory of all Markdown in this repo.  
**中文：** 全仓 Markdown 的英中体例、固定译法与路径分类清单（SSOT）。

**Meta-SSOT exception (this file only):** There is no top-level `## English` here; the paired `**EN:**` / `**中文：**` lines directly under this H1 are intentional for this meta-SSOT. Guides that use top-level `## English` must **not** copy this pattern—follow § B.1 item 1 (no `**中文：**` between H1 and `## English`).

**元 SSOT 例外（仅限本文件）：** 本文件不设顶层 `## English`；H1 下 `**EN:**` / `**中文：**` 双行仅为本体的例导引。凡采用顶层 `## English` 的文档不得照搬此版式，须遵守 § B.1 第 1 条（H1 与 `## English` 之间不放 `**中文：**`）。

---

## Part A — Inventory（46 个 `.md` 路径）

在本文件加入仓库之前，全仓共有 **46** 个 Markdown 文件；加入本文件后为 **47** 个（本文件为体例 SSOT）。其中 `docs/` 目录由原 **35** 篇增至 **36** 篇。

### A.1 contract_manifest_gate 敏感

`python tools/harness.py contract-manifest` 直接读取或强校验子串/表格路径的文档：

| 路径 | 约束摘要 |
| --- | --- |
| `README.md` | 须含 `canonical_error_code`、`failure_type_canonical`、`canonical_reason_codes`；README 内 fenced `python` 示例须满足 `sign_and_broadcast` 与 `Lirix.extract_broadcast_fields` 的语义契约 |
| `docs/release_notes.md` | 须含 `## API Contract Delta` 与 `additive and backward compatible` |
| `docs/api_reference.md` | 多段 API 锚点；异常继承说明须含 gate 要求的中英子串 |
| `docs/architecture_control_plane.md` | 控制面与测试路径锚点 |
| `docs/checklist_implementation_matrix.md` | 含 `CI 显式 governance gate 覆盖 canonical/session/entrypoints/hook/langchain` 等**须原样保留**的行 |
| `docs/audit_path_map.md` | `## Core Assertions Map` 表内路径须真实存在；Governance gate 行测试须在 `ci.yml` 显式 governance 列表中 |
| `docs/tools_gates_index.md` | 主表 harness **子命令**行数须等于 `tools/harness.py` 中 `COMMANDS` 条目数（与 `contract_manifest_gate._count_harness_gate_modules` 对齐） |

另读取非 Markdown：`.github/workflows/ci.yml`、`lirix/core/exceptions.py`、统一客户端实现源。

**Contract substring / 术语锚点核验范围（须与表述一致）：** `canonical_error_code`、`failure_type_canonical`、`canonical_reason_codes` 等 **contract_manifest_gate** 依赖的**字面子串**，以 **§ A.1 表中路径**为限（如 `README.md`、`docs/api_reference.md`、`docs/release_notes.md`、`docs/architecture_control_plane.md` 等）。**不**要求每一篇 `docs/*.md` 都出现上述子串；例如 `docs/quickstart.md` 无这些锚点是正常的，审计或 PR 说明中勿写「所有修改过的 Markdown 都必须可检索到某锚点」之类过宽结论。

**Wave1 高关联**：`docs/ci_gate_matrix.md`（CI/门禁叙事 SSOT；改写须与 `ci.yml` 及上表一致）。

### A.2 根治理（5）

- `README.md`（contract 敏感）
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `REPORT.md`（审计长文：纯英文 H1 + `## English — Executive Summary` + 中文正文自分隔线与中文 `#` 标题起篇；非「仅链接/勘误」类短文）

### A.3 docs/（本文件加入后为 **36**）

除 **A.1** 已标敏感者外，`docs/` 下其余主题文档均为非 contract 子串门禁对象；完整路径以仓库 `docs/**/*.md` 为准（含 `baselines/README.md`、各 ADR、迁移/证据/运维/排障及本 `documentation_styleguide.md`）。

### A.4 audit_artifacts：索引与模板（3）

- `audit_artifacts/README.md`
- `audit_artifacts/release_signoff/README.md`
- `audit_artifacts/release_signoff/B4_local_ci_equivalent_brief.TEMPLATE.md`

### A.5 排除归档（仅极小勘误）（3）

- `audit_artifacts/release_signoff/2026-05-10/B4_local_ci_equivalent_brief.md`
- `audit_artifacts/release_signoff/2026-05-10/C5_coverage_100_verification.md`
- `audit_artifacts/release_signoff/2026-05-10/R1_deprecation_warning_baseline.md`

### A.6 Documentation program freeze（终局冻结 — 仅维护）

**EN:** The dedicated documentation-engineering program is **frozen**: do not add new gate scripts, GitHub workflows, or Markdown-wide architecture refactors as drive-by scope. Subsequent work is **maintenance-only**—keep docs and gate narratives aligned when product or CI behavior changes.

**中文：** 「文档工程」专项目前 **冻结**：请勿以顺带方式扩大范围（新增门禁脚本、工作流或全仓 Markdown 架构重写）。后续仅做 **与产品或 CI 语义变更对齐的维护**。

If you change **Fast Required** order or membership for the document-related harness block (`audit-internal-link`, `doc-preamble-hygiene`, `no-internal-imports`, `root-import-surface`, and immediate neighbors in that sequence), update **in the same PR**:

1. `.github/workflows/ci.yml`
2. `CONTRIBUTING.md` (**both** suggested bash blocks)
3. `tools/release_full_verification.sh` (the docs / import / monkeypatch gate section)
4. `audit_artifacts/release_signoff/README.md` (the step-by-step `tee` example block)

Also verify **`docs/ci_gate_matrix.md`** (Fast Required step narrative) and **`docs/release_pr_checklist.md`** (CI differences / doc preamble bullet) remain **1:1** with `ci.yml`.

若变更 **Fast Required** 中与文档相关 harness 段的 **顺序或集合**（含 `audit-internal-link`、`doc-preamble-hygiene`、`no-internal-imports`、`root-import-surface` 及该段紧邻步骤），须 **同一 PR** 内同步：

1. `.github/workflows/ci.yml`
2. `CONTRIBUTING.md`（**两处**建议 bash 命令块）
3. `tools/release_full_verification.sh`（文档/导入/monkeypatch 门禁段）
4. `audit_artifacts/release_signoff/README.md`（逐步 `tee` 示例块）

并核对 **`docs/ci_gate_matrix.md`**（Fast Required 步骤叙述）与 **`docs/release_pr_checklist.md`**（CI differences / Doc preamble 条目）是否与 `ci.yml` **1:1**。

**校验和（加入本文件后）**：根 5 + `docs/` 36 + audit 活跃 3 + 归档 3 = **47** 个 `.md`；若不计本 styleguide 则仍为 **46**。

---

## Part B — Bilingual structure（整文件 + 小节；与 Part A 不冲突）

### B.1 Three-tier rules — English

0. **Meta-SSOT (`documentation_styleguide.md`):** This file has no top-level `## English`; **one** `**EN:**` line and **one** `**中文：**` line under the H1 (plus the explicit meta-exception note) are allowed **only here**—they document the rules themselves and are not a template for other top-level-split guides.
1. **Whole file (English Complete → Chinese Complete):** When a guide uses top-level `## English` (including `## English — …`) and `## 中文`, keep continuous Chinese prose **after** the first `## 中文`. Between the H1 and `## English`, use at most `**EN:**` plus links; do **not** place `**中文：**` reader lines or long Chinese sentences there (preserves reader flow and gate-friendly anchors).
2. **Subsection-level `### English` / `### 中文`:** Use inside a language region for short mirrored blocks, or in **meta** docs (this file, `docs/tools_gates_index.md`) where a single top-level `## English` / `## 中文` pair is awkward. In **`docs/tools_gates_index.md`**, keep the authoritative **harness subcommand main table**, **Row parity**, and **Convention** text under **`### English`**; use **`### 中文`** for Chinese reader guidance and optional column glosses only. Same pairing may appear under an existing `## English` or `## 中文` parent. Prefer a single fenced code block in the English mirror when duplication is avoidable.
3. **Exemptions:** Bilingual H1 `English / 中文` is allowed for navigation and parity with sibling headings. **`REPORT.md`** uses an **English-only H1**, then `## English — Executive Summary`; the Chinese narrative follows the `---` separator and the Chinese `# …` title block (not mixed into the H1).
4. **Automation (optional):** `python tools/harness.py doc-preamble-hygiene` prints warnings for preamble drift on the default guide paths; pass `--enforce` for a non-zero exit when checks fail (see `docs/tools_gates_index.md`).

### B.1 Three-tier rules — 中文

0. **体例 SSOT（`documentation_styleguide.md`）：** 本文件不设顶层 `## English`；H1 下允许 **各一行** `**EN:**` / `**中文：**`（并附元例外说明），**仅限本 meta 文档**；其他采用顶层 `## English` 的指南不得照搬。
1. **整文件**：采用顶层 `## English` 与 `## 中文` 的指南，连续中文叙述放在 **`## 中文` 之后**；H1 到 `## English` 之间仅用 `**EN:**` 与链接，不放 `**中文：**` 长句（与 Part A 契约路径要求无冲突）。
2. **小节级**：在某一语言区内用 `### English` / `### 中文`（或 `####`）做短对照；体例/索引类文档可主要依赖此层。代码块通常保留在英文侧一份即可。**`docs/tools_gates_index.md`** 的 **Row parity / Convention / 主表** 归 **`### English`**，**`### 中文`** 仅作导读与可选列释义。
3. **豁免**：允许双语 H1（` / `）；审计 **`REPORT.md`** 采用**纯英文 H1** + 英文执行摘要标题，中文正文自分隔线与中文 `#` 标题起篇。
4. **可选门禁**：`python tools/harness.py doc-preamble-hygiene` 对默认指南路径做页眉漂移提示；`--enforce` 失败时非零退出（见 `docs/tools_gates_index.md`）。

**维护注（仓库扫描）：** 使用顶层 `## English`（含 `## English — …`）的 Markdown 目前为 `docs/quickstart.md`、`docs/troubleshooting.md`、`docs/best_practices.md`、`docs/api_reference.md`、`REPORT.md`；`CONTRIBUTING.md` 使用 `## 中文导读` 而无顶层 `## English`，已将 `**中文：**` 置于该节段首。其余 `docs/*.md` 若未采用顶层英中分块，仍适用 § B.2 第 2 条「无 `## English` 时标题下可保留一句 `**中文：**`」。

### B.2 Section template — English

1. **Title** in English (H1), optionally with ` / 中文` on the same line when not using the `REPORT.md` strict H1 rule above.  
2. **`## English` / `## 中文` split files:** put `**中文：**` one-liners at the **start of `## 中文`**, not between H1 and `## English`. **Other layouts** (no top-level `## English`): a one-line `**中文：**` under the H1 remains acceptable.  
3. For each mirrored subsection: use `### English` then `### 中文` (or `#### English` / `#### 中文` under a shared `###` parent). Put code blocks, paths, and API identifiers once—usually in the English block; the Chinese block explains semantics without duplicating fenced code when avoidable.  
4. End with **Related** / **延伸阅读**：bilingual bullets linking to SSOT (`docs/audit_path_map.md`, `docs/quickstart.md`, `docs/api_reference.md`, etc.).  
5. **Do not** change heading slugs that are linked externally; prefer adding bilingual lines under the same heading.

### B.2 Section template — 中文

1. **标题**：英文 H1；若与 `REPORT.md` 体例一致则 H1 纯英文。  
2. **顶层英中分块**：`**中文：**` 放在 **`## 中文` 段首**；无顶层 `## English` 的文档仍可在标题下保留一句 `**中文：**`。  
3. **正文**：每一大节可采用 `### English` 与 `### 中文`（或同级 `####`）；代码与路径通常只保留英文块一份，中文块做语义对照。  
4. **导航**：文末双语链接到 SSOT。  
5. **锚点**：少改 `#` 片段；必要时在同一标题下增译，不强行改 slug。

---

## Part C — Terminology glossary（术语固定译法）

| English / 保留原文 | 中文固定译法 | 备注 |
| --- | --- | --- |
| fail-closed | 失败关闭（fail-closed） | 安全默认不放行 |
| evidence | 证据 / 证据包 | 视上下文选「证据链」 |
| forensic bundle | 取证包 | 字段名保留英文 |
| replay bundle | 重放包 |  |
| governance gate | 治理门禁 | 与 CI step 名区分时写「显式 governance 步骤」 |
| canonical error code | 规范错误码 | 子串 `canonical_error_code` 不译 |
| failure type (canonical) | 规范失败类型 | `failure_type_canonical` 不译 |
| reason code | 原因码 | `canonical_reason_codes` 不译 |
| SSOT | 单一事实来源（SSOT） |  |
| additive and backward compatible | 增量且向后兼容 | `release_notes` 原样英文短语须保留 |
| validate and simulate | 校验并模拟 | API 名保持代码形式 |
| sign and broadcast | 签名并广播 |  |
| Triple-Zero | Triple-Zero（三重零信任叙事） | 品牌语可中英并列一次 |

维护文档时：API 符号、JSON 键、`reason_code` 等**不翻译**；句子层面对照使用上表。

---

### English

Part A is the authoritative inventory and `contract_manifest_gate` sensitivity map; Part B.2–C standardize bilingual edits across the repo.

### 中文

Part A 为路径与契约门禁敏感面的权威清单；Part B.2–C 统一全仓改写时的章节模板与术语，避免译法漂移。
