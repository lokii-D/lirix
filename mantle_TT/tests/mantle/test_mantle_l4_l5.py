import pytest
from lirix import LirixConfig
from lirix.core.exceptions import RPCUnavailableException
from lirix.layers.l4_rpc_manager import RPCManager
from lirix.layers.l5_sandbox_simulator import SandboxSimulator


def test_mantle_l4_spread_fail_closed() -> None:
    config = LirixConfig.for_mantle()
    manager = RPCManager(config)
    with pytest.raises(RPCUnavailableException) as exc:
        manager.sync_reconcile()
    assert "rpc" in str(exc.value).lower() or "spread" in str(exc.value).lower()


def test_mantle_l5_eth_call() -> None:
    simulator = SandboxSimulator()
    with pytest.raises(AttributeError) as exc:
        simulator.simulate(
            {"to": "0x0000000000000000000000000000000000000000", "data": "0x"},
            web3=None,  # type: ignore[arg-type]
            block_number=1,
        )
    assert "eth" in str(exc.value).lower()
