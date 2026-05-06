# SPDX-License-Identifier: MIT
# Copyright (c) 2026 lokii

from __future__ import annotations

from lirix.layers.l3_proxy_piercer import ProxyPiercer


def test_test_proxy_piercer_decode_abi_address_rejects_zero_bad_codec_output() -> None:
    class _Codec:
        def decode(self, types, raw):
            return ("0x0000000000000000000000000000000000000000",)

    class _W3:
        codec = _Codec()

    assert ProxyPiercer._decode_abi_address(_W3(), b"\x00" * 32) is None
