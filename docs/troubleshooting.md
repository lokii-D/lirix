# Troubleshooting / 故障排除


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).

## 🔍 Operator snapshot

Most “breakages” here are **fail-closed by design**: the SDK refused an ambiguous intent, a mismatched allowlist, or a hostile RPC view. Read the exception, tighten config, rerun—**do not** downgrade security exceptions to warnings in business code.

---

## English

### Version errors

Use Python 3.9–3.14 as enforced by `lirix/__init__.py` until support is officially extended.

### Validation exceptions

These usually mean fail-closed behavior. Re-check allowlists, `chain_id`, and that calldata matches declared functions.

### Skipped Anvil tests

Start Anvil on `127.0.0.1:8545` or rely on CI, which starts Anvil automatically.

### mypy vs runtime Python

The mypy target version may differ from the minimum runtime; see `[tool.mypy]` in `pyproject.toml`.

### pip vs pip3

Prefer `python -m pip` to target the correct interpreter in multi-Python setups.

### Multi-version testing (tox)

Use **`tox`** with the environments declared under **`[tool.tox]` in `pyproject.toml`** (`legacy_tox_ini`) to run the same checks across Python versions locally; missing interpreters are skipped when `skip_missing_interpreters` is enabled.

---

## 中文

**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

### `ImportError: Lirix requires Python 3.9 through 3.14`

使用受支持的解释器版本；勿使用 3.8 或 3.15+（除非项目已正式扩展支持）。

### `ConfigurationGuardException` / `InvalidIntentException` 等

属于 **预期内的失败安全行为**。请核对：

- `chain_id` 与合约地址是否一致；
- `allowed_*` 白名单是否覆盖当前 `to` / `function_name` / intent；
- calldata 是否与声明的函数一致。

### 集成测试跳过（Anvil）

若本地运行 `tests/` 中依赖 Anvil 的用例被跳过，请在 `http://127.0.0.1:8545` 启动 Anvil，或参考 CI 工作流。

### CI：Mantle fork 步骤

GitHub Actions 中 Mantle fork 作业依赖仓库 secret `MANTLE_MAINNET_RPC`。未配置时该步骤会跳过（exit 0），主 CI 仍可通过；需要该路径时请在仓库中配置 secret。

### `mypy` 与 Python 3.9+

仓库内 `mypy` 配置以 `pyproject.toml` 的 `[tool.mypy]` 为准，**运行兼容性**以 `requires-python` 为准。

### `pip` vs `pip3`

在仅安装 Python 3 的环境中，`pip` 与 `pip3` 通常等价；若系统存在多个 Python，请显式使用 `python3 -m pip install ...` 指向目标解释器。

### 本地跨版本测试（tox）

推荐使用 **`tox`**（配置见仓库根目录 **`pyproject.toml`** 中的 **`[tool.tox]`**）在本地对齐 CI 的 Python 3.9–3.14 矩阵：安装 dev 依赖后执行 `tox`；未安装的解释器对应环境会被跳过（`skip_missing_interpreters = true`）。
