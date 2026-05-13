# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Concrete L4/L5 construction for the public facade (allowed to import ``lirix.layers``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_sandbox_simulator import SandboxSimulator


@dataclass(frozen=True)
class LirixPipelineLayerExecutor:
    request_timeout: int
    backend_profile: Mapping[str, Any]

    def build_rpc_manager(self, config: Any, hooks: Any) -> RPCManager:
        return RPCManager(config, hooks=hooks, request_timeout=self.request_timeout)

    def build_sandbox_simulator(self, hooks: Any) -> SandboxSimulator:
        return SandboxSimulator(hooks=hooks, backend_profile=dict(self.backend_profile))
