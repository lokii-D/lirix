# Quickstart / 快速开始

## 中文

### 安装

```bash
pip install lirix
# 或
pip3 install lirix
```

开发环境（可编辑安装）：

```bash
pip install -e ".[dev]"
```

### 安全声明（必读）

- **Zero-Key（零私钥）**：本库设计为不接收、不存储、不处理用户私钥或助记词；签名与广播由应用层负责。
- **Fail-Closed**：校验失败时抛出异常并中止；请勿在业务层吞掉安全异常。
- **Zero-Telemetry**：本库不向第三方发送使用统计或遥测数据。

运行时依赖以 `pyproject.toml` 为准（如 `web3`、`eth-abi`、`pydantic`）。本仓库不宣称「零依赖」；若文档其它处出现类似表述，以 `pyproject.toml` 为准。

### 最小示例

```python
from lirix import Lirix, LirixConfig
from web3 import Web3

cfg = LirixConfig(
    chain_id=1,
    strict_mode=False,
    rpc_urls=[],
    allowed_intents=["swap"],
    allowed_function_names=["swapExactTokensForTokens"],
    allowed_to_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
    ],
    whitelisted_addresses=[
        Web3.to_checksum_address("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
    ],
    blacklisted_addresses=[],
)
client = Lirix(cfg)
client.chain_validate(
    "swap",
    {
        "to": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "function_name": "swapExactTokensForTokens",
        "data": "0x...",  # 实际 calldata
    },
)
```

更多示例见仓库 `examples/` 目录。

---

## English

### Install

```bash
pip install lirix
```

Editable install for development:

```bash
pip install -e ".[dev]"
```

### Security notice (required reading)

- **Zero private keys in-library**: Lirix does not accept, store, or process private keys or mnemonics; signing and broadcasting stay in your application.
- **Fail-closed**: validation failures raise exceptions; do not swallow security exceptions in business code.
- **No telemetry**: the SDK does not send usage analytics to third parties.

Runtime dependencies are listed in `pyproject.toml` (e.g. `web3`, `eth-abi`, `pydantic`). This project does **not** claim to be dependency-free at runtime.

### Minimal example

See the Python block above; replace `"0x..."` with real calldata from your integration tests or tooling.

Further samples live under `examples/`.
