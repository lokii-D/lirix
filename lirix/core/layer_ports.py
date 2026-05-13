# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

"""Structural ports for L4/L5 wiring used by ``core`` without importing ``lirix.layers``."""

from __future__ import annotations

from typing import Any, Mapping, Protocol


class RpcEvidenceSource(Protocol):
    """Minimal RPC handle surface required by ``LirixPipelineOrchestrator``."""

    def evidence_snapshot(self) -> Mapping[str, Any]: ...


class PipelineLayerExecutor(Protocol):
    """Factories for L4/L5 objects; implementations live outside ``lirix.core``."""

    def build_rpc_manager(self, config: Any, hooks: Any) -> RpcEvidenceSource: ...

    def build_sandbox_simulator(self, hooks: Any) -> Any: ...
