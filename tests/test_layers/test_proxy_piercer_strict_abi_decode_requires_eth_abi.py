# SPDX-License-Identifier: MIT
from __future__ import annotations

import lirix.layers.l3_proxy_piercer as piercer_mod
import pytest
from lirix.core.exceptions import ConfigurationGuardException
from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_strict_abi_decode_raises_when_eth_abi_decoder_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(piercer_mod, "abi_decode", None)
    piercer = ProxyPiercer(strict_abi_decode=True)

    class _W:
        codec = None

    with pytest.raises(ConfigurationGuardException) as ei:
        piercer._decode_abi_address(_W(), b"\x00" * 32)
    assert ei.value.context.get("dependency") == "eth_abi"
