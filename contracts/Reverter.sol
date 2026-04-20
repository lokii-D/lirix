// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @dev 本地 Anvil 集成测试：可预测 revert 文案
contract Reverter {
    function boom() external pure {
        revert("sandbox_fail");
    }

    function panic() external pure {
        uint256 x = 0;
        uint256 y = 1 / x;
        y;
    }
}
