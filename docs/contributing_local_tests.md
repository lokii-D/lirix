---
title: Contributing — local pytest
purpose: explain pyproject addopts vs single-file runs; editable install prerequisite
---

# 本地测试（贡献者说明）


**EN:** Authoritative technical content in the sections below; repo-wide bilingual conventions: [`documentation_styleguide.md`](documentation_styleguide.md).
**中文：** 正文为权威技术叙述；全仓双语体例见 [`documentation_styleguide.md`](documentation_styleguide.md)。

## 可编辑安装

在仓库根目录运行门禁或与 CI 对齐的 pytest 子集前，请先安装开发依赖（含 `pytest`、`pyyaml` 等）：

```bash
python -m pip install -e ".[dev]"
```

未安装时，部分需要 `import lirix` 的 **`python tools/harness.py …`** 子命令会在运行时失败；详见 `docs/ci_gate_matrix.md` § **Tool gates vs runtime imports** 与 **`docs/tools_gates_index.md`**。

## `pyproject.toml` 里 `addopts` 末尾的 `tests`

`[tool.pytest.ini_options]` 中配置了：

```text
addopts = "... tests --pyargs lirix"
```

末尾的 **`tests` 路径参数** 会作为**默认收集目标**追加到任意 pytest 命令行之后。因此即使你在命令行里只写了一个文件，例如：

```bash
pytest tests/test_core/test_session.py
```

pytest 仍会**同时**收集整个 `tests/` 树（以及 `--pyargs lirix` 带来的 doctest 等），表现为「单文件跑法却像全仓」——这是 **addopts 的设计行为**，不是 pytest 的 bug。

### 推荐：单文件 / 窄子集时清空 addopts

在仓库根目录、已 `pip install -e ".[dev]"` 的前提下：

```bash
pytest -o addopts= tests/test_core/test_session.py
```

等价（pytest 7+）：通过 **`--override-ini`** 清空默认 `addopts`，效果与 `-o addopts=` 相同，任选其一即可：

```bash
pytest --override-ini='addopts=' tests/test_core/test_session.py
```

等价写法示例：

```bash
PYTEST_ADDOPTS= pytest tests/test_core/test_session.py
```

这样会忽略 `pyproject` 里的默认 `addopts`，只收集你显式给出的路径（仍建议保留与 CI 一致的 Python 版本）。

### 全仓与 CI 对齐

需要与 CI Fast Required 中的 **Governance gate** 列表一致时，请直接复制 `.github/workflows/ci.yml` 中 `Governance gate (explicit)` 步骤里的 `pytest` 命令，或使用该列表作为 `pytest` 的文件参数。

更多门禁与 workflow 索引见 **`docs/ci_gate_matrix.md`**。
