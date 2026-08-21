// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @notice A deliberately finite, non-upgradeable positive instance for a
///         global named-acquirer certificate inside a declared toy world.
/// @dev The accompanying model closes the account, control, funding, return,
///      and action universes.  This contract alone is not that global proof.
contract GlobalNamedAcquirerToy {
    error AlreadyOpened();
    error BadMember();
    error BadShare();
    error BadValue();
    error NotBuyer();
    error NotMember();
    error NotOpened();
    error ReplayedShare();
    error TransferFailed();

    uint256 public constant MEMBER_A_AMOUNT = 2 ether;
    uint256 public constant MEMBER_B_AMOUNT = 3 ether;
    uint256 public constant CERTIFIED_OUTFLOW = 5 ether;

    address public immutable buyer;
    address public immutable memberA;
    address public immutable memberB;

    bytes32 public resourceId;
    bytes32 public expectedShareA;
    bytes32 public expectedShareB;
    bytes32 public usableOutputCommitment;

    bool public opened;
    bool public acceptedA;
    bool public acceptedB;
    bool public successful;
    bool private withdrawing;

    mapping(address => uint256) public credit;

    event OrderOpened(address indexed buyer, bytes32 indexed resourceId, uint256 irreversibleDebit);
    event ShareAccepted(address indexed member, bytes32 indexed shareCommitment);
    event UsableOutputCertified(address indexed buyer, bytes32 indexed resourceId, bytes32 outputCommitment);
    event CreditWithdrawn(address indexed member, uint256 amount);

    constructor(address buyer_, address memberA_, address memberB_) {
        if (
            buyer_ == address(0) || memberA_ == address(0) || memberB_ == address(0)
                || buyer_ == memberA_ || buyer_ == memberB_ || memberA_ == memberB_
        ) revert BadMember();
        buyer = buyer_;
        memberA = memberA_;
        memberB = memberB_;
    }

    function open(bytes32 resourceId_, bytes32 shareA_, bytes32 shareB_) external payable {
        if (msg.sender != buyer) revert NotBuyer();
        if (opened) revert AlreadyOpened();
        if (msg.value != CERTIFIED_OUTFLOW) revert BadValue();
        if (resourceId_ == bytes32(0) || shareA_ == bytes32(0) || shareB_ == bytes32(0)) revert BadShare();

        opened = true;
        resourceId = resourceId_;
        expectedShareA = shareA_;
        expectedShareB = shareB_;
        emit OrderOpened(msg.sender, resourceId_, msg.value);
    }

    function submitShare(bytes32 shareCommitment) external {
        if (!opened) revert NotOpened();
        if (msg.sender == memberA) {
            if (acceptedA) revert ReplayedShare();
            if (shareCommitment != expectedShareA) revert BadShare();
            acceptedA = true;
        } else if (msg.sender == memberB) {
            if (acceptedB) revert ReplayedShare();
            if (shareCommitment != expectedShareB) revert BadShare();
            acceptedB = true;
        } else {
            revert NotMember();
        }
        emit ShareAccepted(msg.sender, shareCommitment);

        if (acceptedA && acceptedB) {
            successful = true;
            credit[memberA] = MEMBER_A_AMOUNT;
            credit[memberB] = MEMBER_B_AMOUNT;
            usableOutputCommitment = keccak256(abi.encode(resourceId, expectedShareA, expectedShareB, buyer));
            emit UsableOutputCertified(buyer, resourceId, usableOutputCommitment);
        }
    }

    function withdrawCredit() external {
        if (msg.sender != memberA && msg.sender != memberB) revert NotMember();
        uint256 amount = credit[msg.sender];
        if (amount == 0) revert BadValue();
        if (withdrawing) revert TransferFailed();
        credit[msg.sender] = 0;
        withdrawing = true;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        withdrawing = false;
        if (!ok) revert TransferFailed();
        emit CreditWithdrawn(msg.sender, amount);
    }
}
