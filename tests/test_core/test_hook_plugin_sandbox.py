# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import Any, Dict, List

from lirix import Lirix, LirixConfig
from lirix.core.constants import HOOK_PRE_SIMULATION


def test_pre_simulation_plugin_is_decoupled_from_core() -> None:
    """沙盒插件：仅依赖 Hook 约定与 kwargs，不 import 核心业务实现。"""

    class _SandboxPlugin:
        def __init__(self) -> None:
            self.seen: List[Dict[str, Any]] = []

        def on_pre_simulation(self, *args: object, **kwargs: object) -> str:
            self.seen.append(dict(kwargs))
            return "sandbox_ok"

    plugin = _SandboxPlugin()
    cfg = LirixConfig(chain_id=1, strict_mode=False)
    client = Lirix(cfg)
    client.hooks.register_hook(HOOK_PRE_SIMULATION, plugin.on_pre_simulation)

    out = client.hooks.invoke_hooks(
        HOOK_PRE_SIMULATION,
        tx_draft_id="draft-1",
        calldata=b"\x12\x34",
    )
    assert out == ["sandbox_ok"]
    assert plugin.seen[0]["tx_draft_id"] == "draft-1"
    assert plugin.seen[0]["calldata"] == b"\x12\x34"
