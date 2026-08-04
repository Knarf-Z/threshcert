// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IThresholdSetRegistry, IUsableShareVerifier} from "../PrefundedThresholdExchange.sol";

contract MockThresholdSetRegistry is IThresholdSetRegistry {
    bool public allowed = true;

    function setAllowed(bool value) external {
        allowed = value;
    }

    function isThresholdSet(bytes32, uint64, address buyer, address[] calldata members)
        external
        view
        returns (bool)
    {
        if (!allowed || buyer == address(0) || members.length == 0) return false;
        for (uint256 i; i < members.length; ++i) {
            if (members[i] == address(0) || members[i] == buyer) return false;
        }
        return true;
    }
}

contract MockUsableShareVerifier is IUsableShareVerifier {
    bool public allowed = true;

    function setAllowed(bool value) external {
        allowed = value;
    }

    function verifyShare(bytes32, address buyer, address member, bytes32 commitment, bytes calldata proof)
        external
        view
        returns (bool)
    {
        return allowed && buyer != address(0) && member != address(0) && commitment != bytes32(0)
            && keccak256(proof) == keccak256("valid-proof");
    }
}

