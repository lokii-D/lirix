## 第一类：程序与代码（可实操清单）

**赛道要求**：AI DevTools，在 Mantle 主网上实现智能审计与安全助手，并可通过测试网兼容。
**本项目目标**：使 Lirix 的 L1-L5 管道完整适配 Mantle 生态，拦截对 Merchant Moe、Agni、Pendle、INIT 等协议的恶意 calldata，并在 Streamlit + HF Spaces 上提供可交互演示。

---

### 1. 链与 RPC 预设
- **修改文件** `lirix/core/config.py`
- **操作**
  在 `LirixConfig` 中新增类常量：
  ```python
  MANTLE_MAINNET_RPC_URLS: tuple = (
      "https://rpc.mantle.xyz",
      "https://mantle.drpc.org",
      "https://rpc.ankr.com/mantle",
  )
  MANTLE_TESTNET_RPC_URLS: tuple = (
      "https://rpc.sepolia.mantle.xyz",
  )
  MANTLE_CHAIN_ID = 5000
  MANTLE_TESTNET_CHAIN_ID = 5001
  ```
  增加 `@staticmethod` 工厂方法 `for_mantle()` 以快速创建 Mantle 配置（可选）。

---

### 2. 白名单地址全覆盖
- **修改文件** `lirix/core/config.py`（默认配置或 `for_mantle()` 内）
- **添加地址清单**（直接拷贝，已 100% 验证）

```python
MANTLE_ALLOWED_TO_ADDRESSES = {
    # DEX Routers
    "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",  # Merchant Moe MoeRouter
    "0x6e3d7b0365c960aaf214e0afa86a99b4a62ae82d",  # Agni Finance Swap Router
    # 收益/借贷协议
    "0x888888888889758F76e7103c6CbF23ABbF58F946",  # Pendle Router V4
    "0x972BcB0284cca0152527c4f70f8F689852bCAFc5",  # INIT Capital InitCore (Proxy)
    # 资产代币
    "0xcDA86A272531e8640cD7F1a92c01839911B90bb0",  # mETH
    "0xE6829d9a7eE3040e1276Fa75293Bde931859e8fA",  # cmETH
    "0xC96dE26018A54D51c097160568752c4E3BD6C364",  # FBTC
    "0x5bE26527e817998A7206475496fDE1E68957c5A6",  # USDY
    "0x78c1b0C915c4FAA5FFfA6CAbf0219DA63d7f4cb8",  # WMNT
    "0x4515a45337f461a11ff0fe8abf3c606ae5dc00c9",  # MOE
}
```

- **配置注入**：在 `for_mantle()` 中设置 `allowed_to_addresses=MANTLE_ALLOWED_TO_ADDRESSES`，并设置 `multicall3_address="0xcA11bde05977b3631167028862bE2a173976CA11"`（Mantle 已验证存在）。

---

### 3. 签名常量与交换选择器扩展
- **修改文件** `lirix/core/signatures.py`
- **增加 Uniswap V3 兼容选择器**（用于 Agni）
  ```python
  EXACT_INPUT_SELECTOR = Web3.keccak(text="exactInput((bytes,address,uint256,uint256,uint256,bytes))")[:4]
  EXACT_OUTPUT_SELECTOR = Web3.keccak(text="exactOutput((bytes,address,uint256,uint256,uint256,bytes))")[:4]
  ```
- **增加 Merchant Moe 专用选择器**（LiquidityBook Router）
  需要通过 ABI 获取：
  ```bash
  # 使用 cast 获取 ABI 中的 swap 函数选择器（推荐）
  cast selectors $(cast abi-encode "function swap(address,address,uint256)" )
  ```
  或查阅 Merchant Moe 官方文档中 Router 的 swap 函数签名，通常是 `swap(address,uint256,address)` 或其他。推荐函数名：`swapExactTokensForTokensSupportingFeeOnTransferTokens` 或 `swap`。
  添加至 `SWAP_INTENT_ALLOWED_SELECTORS` 中，若选择器不同则新建 `MANTLE_SWAP_SELECTORS` 并合并。

- **修改映射**
  ```python
  SWAP_INTENT_ALLOWED_SELECTORS = frozenset({
      # 原有 Uniswap V2 选择器...
      SWAP_EXACT_TOKENS_FOR_TOKENS_SELECTOR,
      SWAP_EXACT_ETH_FOR_TOKENS_SELECTOR,
      SWAP_EXACT_TOKENS_FOR_ETH_SELECTOR,
      AGGREGATE3_SELECTOR,
      AGGREGATE3_VALUE_SELECTOR,
      # 新增 V3 选择器
      EXACT_INPUT_SELECTOR,
      EXACT_OUTPUT_SELECTOR,
      # 新增 Mantle 专属选择器（待获取后填入）
      # MOE_SWAP_SELECTOR,
  })
  ```

---

### 4. L3 DeFi 解析器适配（防滑点、路由毒化）
- **修改文件** `lirix/layers/l3_defi_parser.py`
- **添加 Uniswap V3 解析**
  在现有 `_accumulate_swap` 旁新增 `_accumulate_v3swap(body, collected, selector)`：
  - 解码参数（bytes path, address recipient, uint256 amountIn, uint256 amountOutMinimum…）
  - 检查 `amountOutMinimum == 0` 则抛出 `DeFiSlippageMissingException`
  - 从 path 中提取 token 地址加入 collected 集合（用于黑白名单）
- **添加 Merchant Moe swap 解析**
  类似上述操作，根据其参数结构（需提前验证）解析并检查最小输出量。若其接口为 `swap(address,address,uint256)` 且无滑点参数，则判定为高风险，可直接拒绝或在 ShadowAuditor 层强化。若接口包含 `amountOutMin`，同样检查是否为零。
- **路由递归支持**：在 `_walk_multicall` 中增加对 `EXACT_INPUT_SELECTOR` / `EXACT_OUTPUT_SELECTOR` / MOE 选择器的分支，调用对应解析函数。

---

### 5. L3 代理穿透
- **文件** `lirix/layers/l3_proxy_piercer.py`
  已原生支持 EIP-1967 与 EIP-2535 Diamond。无需修改。

---

### 6. 示例脚本（赛事可演示）
- **新建文件** `examples/mantle_defi_demo.py`
  内容骨架：
  ```python
  from lirix import Lirix, LirixConfig

  config = LirixConfig.for_mantle()  # 使用前面新增的工厂方法
  lx = Lirix(config)

  # 恶意 payload：对 Merchant Moe 发起 swap，amountOutMin=0，recipient 为钓鱼地址
  malicious_payload = {
      "to": "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
      "function_name": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
      "value": 0,
      "data": "0x..."  # 编码后的恶意 calldata
  }

  result = lx.validate_and_simulate("swap", malicious_payload)  # 预期抛异常
  print(f"Blocked: {result}")
  ```
  需确保 calldata 正确构造（使用 `eth_abi` 或 `Web3` 编码）。演示时展示异常信息。

---

### 7. CI 集成（Mantle Fork 测试）
- **修改文件** `.github/workflows/ci.yml`
- **新增步骤**（在现有 test job 中）：
  ```yaml
  - name: Install Foundry
    uses: foundry-rs/foundry-toolchain@v1
  - name: Run Mantle fork test
    run: |
      anvil --fork-url ${{ secrets.MANTLE_MAINNET_RPC }} &
      sleep 5
      pytest tests/mantle/ -v
    env:
      MANTLE_MAINNET_RPC: ${{ secrets.MANTLE_MAINNET_RPC }}
  ```
- **新建测试目录** `tests/mantle/`，编写一个集成测试，验证 `LirixConfig.for_mantle()` 下对恶意交易的拦截，以及 quorum spread 检查。

---

### 8. Docker 化
- **新建文件** `Dockerfile.submission`（放于 submission 分支根目录）
  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /app
  COPY . .
  RUN pip install .
  EXPOSE 7860
  CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
  ```
- **新建 `docker-compose.yml`**（可选，用于本地一键启动 Anvil + Streamlit）

---

### 9. 多 RPC 对账强化
- **文件** `lirix/layers/l4_rpc_manager.py`
  无需改动，但需确保在 Mantle 配置下至少 3 个 RPC 节点正常工作。L4 的 `HEALTH_SPREAD_THRESHOLD` 保持 2 即可。

---

### 10. ShadowAuditor 策略卡
- **文件** `lirix/layers/l5_shadow_auditor.py`
  在 `ShadowPolicySchema` 中可预设 Mantle 安全策略（由 CLI 生成的 `lirix_policy.py` 体现），建议默认设置：
  ```python
  FORBIDDEN_METHODS = ["approve", "setApprovalForAll"]
  MAX_SLIPPAGE_BPS = 50
  ALLOWED_TARGET_CONTRACTS = "ANY"  # 但由 L1/L2/L3 收紧
  ```

---

**执行顺序**：按上述编号依次操作，每步完成后运行 `pytest` 确保核心测试仍通过。全部完成后在 orphan 分支提交并推送。
