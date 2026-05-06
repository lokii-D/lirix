from __future__ import annotations

import pytest
from lirix.layers.l4_rpc_manager import AsyncQuorumProvider, LirixConsensusFailureException


@pytest.mark.asyncio
async def test_quorum_eth_call_rejects_empty_rpc_urls_with_consensus_failure() -> None:
    provider = AsyncQuorumProvider([])
    with pytest.raises(LirixConsensusFailureException, match="LRX_L4_CONSENSUS_FAILED"):
        await provider.quorum_eth_call({"to": "0x1"})
