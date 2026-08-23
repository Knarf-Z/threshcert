// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IShareVerifier {
    function verifyShare(
        uint256 offerId,
        address member,
        bytes calldata share,
        bytes calldata proof
    ) external view returns (bool);
}

contract AtomicBypassEscrow {
    struct Offer {
        address buyer;
        uint256 paymentPerMember;
        uint256 deadline;
        uint256 requiredMembers;
        uint256 acceptedMembers;
        bool settled;
    }

    uint256 public immutable packageSizeLimit;
    uint256 public immutable invocationLimit;
    IShareVerifier public immutable shareVerifier;
    uint256 public invocations;
    uint256 public nextOfferId;

    mapping(uint256 => Offer) public offers;
    mapping(uint256 => address[]) private offerMembers;
    mapping(uint256 => mapping(address => bool)) public targeted;
    mapping(uint256 => mapping(address => bool)) public accepted;
    mapping(uint256 => mapping(bytes32 => bool)) public usedShareCommitment;

    event OfferCreated(uint256 indexed offerId, uint256 requiredMembers);
    event Accepted(uint256 indexed offerId, address indexed member);
    event Settled(uint256 indexed offerId);

    constructor(
        uint256 packageSizeLimit_,
        uint256 invocationLimit_,
        IShareVerifier shareVerifier_
    ) {
        require(packageSizeLimit_ > 0, "zero package limit");
        require(invocationLimit_ > 0, "zero invocation limit");
        require(address(shareVerifier_) != address(0), "zero verifier");
        packageSizeLimit = packageSizeLimit_;
        invocationLimit = invocationLimit_;
        shareVerifier = shareVerifier_;
    }

    function createOffer(
        address[] calldata requiredMembers,
        uint256 paymentPerMember,
        uint256 deadline
    ) external payable returns (uint256 offerId) {
        require(invocations < invocationLimit, "global invocation limit");
        require(requiredMembers.length > 0, "empty package");
        require(requiredMembers.length <= packageSizeLimit, "package too large");
        require(paymentPerMember > 0, "zero payment");
        require(deadline > block.timestamp, "bad deadline");
        require(
            msg.value == requiredMembers.length * paymentPerMember,
            "bad escrow"
        );

        invocations += 1;
        offerId = nextOfferId++;
        offers[offerId] = Offer({
            buyer: msg.sender,
            paymentPerMember: paymentPerMember,
            deadline: deadline,
            requiredMembers: requiredMembers.length,
            acceptedMembers: 0,
            settled: false
        });
        for (uint256 i = 0; i < requiredMembers.length; ++i) {
            address member = requiredMembers[i];
            require(member != address(0), "zero member");
            require(!targeted[offerId][member], "duplicate target");
            targeted[offerId][member] = true;
            offerMembers[offerId].push(member);
        }
        emit OfferCreated(offerId, requiredMembers.length);
    }

    function accept(
        uint256 offerId,
        bytes calldata share,
        bytes calldata proof
    ) external {
        Offer storage offer = offers[offerId];
        require(offer.buyer != address(0), "unknown offer");
        require(block.timestamp <= offer.deadline, "expired");
        require(!offer.settled, "settled");
        require(targeted[offerId][msg.sender], "not targeted");
        require(!accepted[offerId][msg.sender], "duplicate");
        require(share.length > 0, "empty share");
        require(
            shareVerifier.verifyShare(offerId, msg.sender, share, proof),
            "invalid share"
        );
        bytes32 commitment = keccak256(share);
        require(
            !usedShareCommitment[offerId][commitment],
            "duplicate share commitment"
        );

        usedShareCommitment[offerId][commitment] = true;
        accepted[offerId][msg.sender] = true;
        offer.acceptedMembers += 1;
        emit Accepted(offerId, msg.sender);
    }

    function settle(uint256 offerId) external {
        Offer storage offer = offers[offerId];
        require(offer.buyer != address(0), "unknown offer");
        require(!offer.settled, "settled");
        require(offer.acceptedMembers == offer.requiredMembers, "incomplete package");

        offer.settled = true;
        address[] storage members = offerMembers[offerId];
        for (uint256 i = 0; i < members.length; ++i) {
            require(accepted[offerId][members[i]], "non-accepting member");
            (bool ok,) = payable(members[i]).call{
                value: offer.paymentPerMember
            }("");
            require(ok, "payment failed");
        }
        emit Settled(offerId);
    }

    function getOfferMembers(
        uint256 offerId
    ) external view returns (address[] memory) {
        return offerMembers[offerId];
    }

    function refundExpired(uint256 offerId) external {
        Offer storage offer = offers[offerId];
        require(offer.buyer != address(0), "unknown offer");
        require(msg.sender == offer.buyer, "not buyer");
        require(block.timestamp > offer.deadline, "not expired");
        require(!offer.settled, "settled");
        offer.settled = true;
        (bool ok,) = payable(offer.buyer).call{
            value: offer.requiredMembers * offer.paymentPerMember
        }("");
        require(ok, "refund failed");
    }
}
