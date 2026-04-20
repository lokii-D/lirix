# Troubleshooting / 故障排除

## 中文

### `ImportError: Lirix requires Python 3.8 through 3.12`

使用受支持的解释器版本；勿使用 3.7 或 3.13+（除非项目已正式扩展支持）。

### `ConfigurationGuardException` / `InvalidIntentException` 等

属于 **预期内的失败安全行为**。请核对：

- `chain_id` 与合约地址是否一致；
- `allowed_*` 白名单是否覆盖当前 `to` / `function_name` / intent；
- calldata 是否与声明的函数一致。

### 集成测试跳过（Anvil）

若本地运行 `tests/` 中依赖 Anvil 的用例被跳过，请在 `http://127.0.0.1:8545` 启动 Anvil，或参考 CI 工作流。

### `mypy` 与 Python 3.8

较新版本 `mypy` 的类型检查目标可能高于 3.8；仓库内 `mypy` 配置以 `pyproject.toml` / `.mypy.ini` 为准，**运行兼容性**仍以 `requires-python` 为准。

### `pip` vs `pip3`

在仅安装 Python 3 的环境中，`pip` 与 `pip3` 通常等价；若系统存在多个 Python，请显式使用 `python3 -m pip install ...` 指向目标解释器。

### 本地跨版本测试（tox）

推荐使用 **`tox`**（见仓库根目录 `tox.ini`）在本地对齐 CI 的 Python 3.8–3.12 矩阵：安装 dev 依赖后执行 `tox`；未安装的解释器对应环境会被跳过（`skip_missing_interpreters = true`）。

---

## English

### Version errors

Use Python 3.8–3.12 as enforced by `lirix/__init__.py` until support is officially extended.

### Validation exceptions

These usually mean fail-closed behavior. Re-check allowlists, `chain_id`, and that calldata matches declared functions.

### Skipped Anvil tests

Start Anvil on `127.0.0.1:8545` or rely on CI, which starts Anvil automatically.

### mypy vs runtime Python

The mypy target version may differ from the minimum runtime; see `.mypy.ini` comments.

### pip vs pip3

Prefer `python -m pip` to target the correct interpreter in multi-Python setups.

### Multi-version testing (tox)

Use **`tox`** per `tox.ini` to run the same checks across Python versions locally; missing interpreters are skipped when `skip_missing_interpreters` is enabled.
