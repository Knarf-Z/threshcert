// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

interface IThresholdSetRegistry {
    function isThresholdSet(
        bytes32 committeeId,
        uint64 epoch,
        address buyer,
        address[] calldata members
    ) external view returns (bool);
}

interface IUsableShareVerifier {
    function verifyShare(
        bytes32 orderId,
        address buyer,
        address member,
        bytes32 shareCommitment,
        bytes calldata proof
    ) external view returns (bool);
}

/// @notice A deliberately narrow positive bridge construction.
/// @dev The immutable registry and verifier are part of the admitted scope.
///      There is intentionally no cancellation, buyer refund, upgrade hook,
///      delegate call, fallback, or external adapter.
contract PrefundedThresholdExchange {
    error BadThresholdSet();
    error BadValue();
    error EmptyOrder();
    error InvalidShare();
    error NotMember();
    error ReplayedShare();
    error TransferFailed();
    error ZeroAmount();

    struct Order {
        address buyer;
        bytes32 committeeId;
        uint64 epoch;
        uint32 accepted;
        uint32 memberCount;
        uint256 prefunded;
        bool successful;
    }

    IThresholdSetRegistry public immutable registry;
    IUsableShareVerifier public immutable verifier;
    uint256 public nextNonce;

    mapping(bytes32 => Order) public orders;
    mapping(bytes32 => mapping(address => uint256)) public promised;
    mapping(bytes32 => mapping(address => bool)) public accepted;
    mapping(address => uint256) public credit;

    bool private withdrawing;

    event OrderOpened(
        bytes32 indexed orderId,
        address indexed buyer,
        bytes32 indexed committeeId,
        uint64 epoch,
        uint256 prefunded,
        address[] members,
        uint256[] amounts
    );
    event ShareAccepted(bytes32 indexed orderId, address indexed member, bytes32 shareCommitment, uint256 credit);
    event OrderSucceeded(bytes32 indexed orderId, address indexed buyer, uint256 certifiedOutflow);
    event CreditWithdrawn(address indexed member, uint256 amount);

    constructor(IThresholdSetRegistry registry_, IUsableShareVerifier verifier_) {
        registry = registry_;
        verifier = verifier_;
    }

    function openOrder(
        bytes32 committeeId,
        uint64 epoch,
        address[] calldata members,
        uint256[] calldata amounts
    ) external payable returns (bytes32 orderId) {
        uint256 length = members.length;
        if (length == 0 || length != amounts.length) revert EmptyOrder();
        if (!registry.isThresholdSet(committeeId, epoch, msg.sender, members)) revert BadThresholdSet();

        uint256 total;
        for (uint256 i; i < length; ++i) {
            if (amounts[i] == 0) revert ZeroAmount();
            for (uint256 j; j < i; ++j) {
                if (members[i] == members[j]) revert BadThresholdSet();
            }
            total += amounts[i];
        }
        if (msg.value != total) revert BadValue();

        uint256 nonce = nextNonce++;
        orderId = keccak256(abi.encode(address(this), block.chainid, msg.sender, committeeId, epoch, members, amounts, nonce));
        orders[orderId] = Order({
            buyer: msg.sender,
            committeeId: committeeId,
            epoch: epoch,
            accepted: 0,
            memberCount: uint32(length),
            prefunded: total,
            successful: false
        });
        for (uint256 i; i < length; ++i) promised[orderId][members[i]] = amounts[i];
        emit OrderOpened(orderId, msg.sender, committeeId, epoch, total, members, amounts);
    }

    function submitShare(bytes32 orderId, bytes32 shareCommitment, bytes calldata proof) external {
        Order storage order = orders[orderId];
        uint256 amount = promised[orderId][msg.sender];
        if (amount == 0) revert NotMember();
        if (accepted[orderId][msg.sender]) revert ReplayedShare();
        if (!verifier.verifyShare(orderId, order.buyer, msg.sender, shareCommitment, proof)) revert InvalidShare();

        accepted[orderId][msg.sender] = true;
        order.accepted += 1;
        credit[msg.sender] += amount;
        emit ShareAccepted(orderId, msg.sender, shareCommitment, amount);

        if (order.accepted == order.memberCount) {
            order.successful = true;
            emit OrderSucceeded(orderId, order.buyer, order.prefunded);
        }
    }

    function withdrawCredit() external {
        if (withdrawing) revert TransferFailed();
        uint256 amount = credit[msg.sender];
        if (amount == 0) revert BadValue();
        credit[msg.sender] = 0;
        withdrawing = true;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        withdrawing = false;
        if (!ok) revert TransferFailed();
        emit CreditWithdrawn(msg.sender, amount);
    }
}

