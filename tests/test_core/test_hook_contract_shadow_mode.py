from __future__ import annotations

from lirix.core.constants import HOOK_PRE_VALIDATE
from lirix.core.hook_contract import HookPatch
from lirix.core.hook_manager import HookManager


def test_shadow_mode_disables_patch_application() -> None:
    mgr = HookManager(contract_mode="shadow")
    payload = {"a": 1}

    def patcher(*args: object, **kwargs: object) -> HookPatch:
        return HookPatch(updates={"b": 2}, reason="shadow")

    mgr.register_hook(HOOK_PRE_VALIDATE, patcher)
    out = mgr.invoke_hooks_isolated(HOOK_PRE_VALIDATE, intent="swap", payload=payload)
    assert out[0]["ok"] is True
    assert out[0]["patch_allowed"] is False
    assert out[0]["shadow_only"] is True
    assert "b" not in payload
