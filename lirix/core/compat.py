# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from typing import (
    Any,
)
from typing import (
    get_args as _get_args,
)
from typing import (
    get_origin as _get_origin,
)
from typing import (
    get_type_hints as _get_type_hints,
)

__all__ = ["get_args", "get_origin", "get_type_hints"]


def get_type_hints(
    obj: Any,
    /,
    *,
    globalns: dict[str, Any] | None = None,
    localns: dict[str, Any] | None = None,
    include_extras: bool = False,
) -> dict[str, Any]:
    """Python 3.9–3.14+ compatible wrapper for runtime reflection helpers."""
    return _get_type_hints(
        obj,
        globalns=globalns,
        localns=localns,
        include_extras=include_extras,
    )


def get_origin(tp: Any, /) -> Any:
    return _get_origin(tp)


def get_args(tp: Any, /) -> tuple[Any, ...]:
    return _get_args(tp)
