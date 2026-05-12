"""Backward-compatible re-exports; prefer :mod:`lirix.core.client_components`."""

from __future__ import annotations

from lirix.core.client_components import (
    RequestContext,
    error_to_feedback_mapper,
    pipeline_orchestrator,
    request_normalization,
    result_envelope_builder,
)

__all__ = [
    "RequestContext",
    "error_to_feedback_mapper",
    "pipeline_orchestrator",
    "request_normalization",
    "result_envelope_builder",
]
