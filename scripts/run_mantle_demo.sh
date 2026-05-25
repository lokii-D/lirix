#!/bin/bash
set -euo pipefail

echo "🚀 Lirix 2.0.4 Mantle Demo 启动..."
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate

pip install -e ".[dev]" --quiet

echo "✅ 运行 2.0.4 validate_and_simulate（恶意 → 拦截 → Failure Protocol）"
python - <<'PY'
from lirix import Lirix, LirixConfig

config = LirixConfig.for_mantle() if hasattr(LirixConfig, "for_mantle") else LirixConfig()
lx = Lirix(config)
malicious = {
    "to": "0xeaEE7EE68874218c3558b40063c42B82D3E7232a",
    "function_name": "swap",
    "data": "0x...",
    "value": 0,
}
result = lx.validate_and_simulate("swap", malicious)
print("=== 2.0.4 Orchestrator Result ===")
import json
print(json.dumps(result, indent=2, default=str))
PY

echo "🎉 Demo 完成！现在打开 http://localhost:8501 查看可视化界面"
