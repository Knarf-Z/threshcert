// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/AtomicBypassEscrow.sol";

interface Vm {
    function warp(uint256 timestamp) external;
}

contract MockShareVerifier is IShareVerifier {
    mapping(bytes32 => bool) private valid;

    function key(
        uint256 offerId,
        address member,
        bytes memory share
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(offerId, member, keccak256(share)));
    }

    function setValid(
        uint256 offerId,
        address member,
        bytes memory share,
        bool isValid
    ) external {
        valid[key(offerId, member, share)] = isValid;
    }

    function verifyShare(
        uint256 offerId,
        address member,
        bytes calldata share,
        bytes calldata
    ) external view returns (bool) {
        return valid[key(offerId, member, share)];
    }
}

contract Receiver {
    function accept(
        AtomicBypassEscrow escrow,
        uint256 offerId,
        bytes calldata share
    ) external {
        escrow.accept(offerId, share, "");
    }

    function acceptWithProof(
        AtomicBypassEscrow escrow,
        uint256 offerId,
        bytes calldata share,
        bytes calldata proof
    ) external {
        escrow.accept(offerId, share, proof);
    }

    function refund(AtomicBypassEscrow escrow, uint256 offerId) external {
        escrow.refundExpired(offerId);
    }

    receive() external payable {}
}

contract RejectingReceiver {
    function accept(
        AtomicBypassEscrow escrow,
        uint256 offerId,
        bytes calldata share
    ) external {
        escrow.accept(offerId, share, "");
    }

    receive() external payable {
        revert("reject payment");
    }
}

contract AtomicBypassEscrowTest {
    Vm private constant vm =
        Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    receive() external payable {}

    function deploy(
        uint256 packageLimit,
        uint256 invocationLimit
    ) internal returns (
        AtomicBypassEscrow escrow,
        MockShareVerifier verifier
    ) {
        verifier = new MockShareVerifier();
        escrow = new AtomicBypassEscrow(
            packageLimit,
            invocationLimit,
            verifier
        );
    }

    function pair(
        address a,
        address b
    ) internal pure returns (address[] memory members) {
        members = new address[](2);
        members[0] = a;
        members[1] = b;
    }

    function singleton(
        address a
    ) internal pure returns (address[] memory members) {
        members = new address[](1);
        members[0] = a;
    }

    function authorize(
        MockShareVerifier verifier,
        uint256 offerId,
        address member,
        bytes memory share
    ) internal {
        verifier.setValid(offerId, member, share, true);
    }

    function testAtomicSettlement() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(2, 1);
        Receiver a = new Receiver();
        Receiver b = new Receiver();
        uint256 offerId = escrow.createOffer{value: 2 wei}(
            pair(address(a), address(b)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, offerId, address(a), hex"01");
        authorize(verifier, offerId, address(b), hex"02");
        a.accept(escrow, offerId, hex"01");
        b.accept(escrow, offerId, hex"02");
        escrow.settle(offerId);
        require(address(a).balance == 1 wei, "a unpaid");
        require(address(b).balance == 1 wei, "b unpaid");
    }

    function testIncompletePackageCannotSettle() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(2, 1);
        Receiver a = new Receiver();
        Receiver b = new Receiver();
        uint256 offerId = escrow.createOffer{value: 2 wei}(
            pair(address(a), address(b)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, offerId, address(a), hex"01");
        a.accept(escrow, offerId, hex"01");
        (bool ok,) = address(escrow).call(
            abi.encodeCall(escrow.settle, (offerId))
        );
        require(!ok, "partial package settled");
    }

    function testGlobalInvocationLimit() public {
        (AtomicBypassEscrow escrow,) = deploy(1, 1);
        Receiver a = new Receiver();
        address[] memory members = singleton(address(a));
        escrow.createOffer{value: 1 wei}(
            members,
            1 wei,
            block.timestamp + 1 days
        );
        (bool ok,) = address(escrow).call{value: 1 wei}(
            abi.encodeCall(
                escrow.createOffer,
                (members, 1 wei, block.timestamp + 1 days)
            )
        );
        require(!ok, "invocation limit bypassed");
    }

    function testPackageSizeLimit() public {
        (AtomicBypassEscrow escrow,) = deploy(2, 1);
        Receiver a = new Receiver();
        Receiver b = new Receiver();
        Receiver c = new Receiver();
        address[] memory members = new address[](3);
        members[0] = address(a);
        members[1] = address(b);
        members[2] = address(c);
        (bool ok,) = address(escrow).call{value: 3 wei}(
            abi.encodeCall(
                escrow.createOffer,
                (members, 1 wei, block.timestamp + 1 days)
            )
        );
        require(!ok, "oversized package accepted");
    }

    function testNonTargetCannotAccept() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(1, 1);
        Receiver target = new Receiver();
        Receiver outsider = new Receiver();
        uint256 offerId = escrow.createOffer{value: 1 wei}(
            singleton(address(target)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, offerId, address(outsider), hex"01");
        (bool ok,) = address(outsider).call(
            abi.encodeCall(
                outsider.accept,
                (escrow, offerId, bytes(hex"01"))
            )
        );
        require(!ok, "non-target accepted");
    }

    function testDuplicateCommitmentRejected() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(2, 1);
        Receiver a = new Receiver();
        Receiver b = new Receiver();
        uint256 offerId = escrow.createOffer{value: 2 wei}(
            pair(address(a), address(b)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, offerId, address(a), hex"01");
        authorize(verifier, offerId, address(b), hex"01");
        a.accept(escrow, offerId, hex"01");
        (bool ok,) = address(b).call(
            abi.encodeCall(b.accept, (escrow, offerId, bytes(hex"01")))
        );
        require(!ok, "duplicate commitment accepted");
    }

    function testRepeatedSingletonPackages() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(1, 2);
        Receiver a = new Receiver();
        Receiver b = new Receiver();
        uint256 first = escrow.createOffer{value: 1 wei}(
            singleton(address(a)),
            1 wei,
            block.timestamp + 1 days
        );
        uint256 second = escrow.createOffer{value: 1 wei}(
            singleton(address(b)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, first, address(a), hex"01");
        authorize(verifier, second, address(b), hex"02");
        a.accept(escrow, first, hex"01");
        b.accept(escrow, second, hex"02");
        escrow.settle(first);
        escrow.settle(second);
        require(escrow.invocations() == 2, "wrong invocation count");
        require(address(a).balance == 1 wei, "a unpaid");
        require(address(b).balance == 1 wei, "b unpaid");
    }

    function testUnknownOfferCannotSettle() public {
        (AtomicBypassEscrow escrow,) = deploy(1, 1);
        (bool ok,) = address(escrow).call(
            abi.encodeCall(escrow.settle, (999))
        );
        require(!ok, "unknown offer settled");
    }

    function testZeroPaymentRejected() public {
        (AtomicBypassEscrow escrow,) = deploy(1, 1);
        Receiver a = new Receiver();
        (bool ok,) = address(escrow).call(
            abi.encodeCall(
                escrow.createOffer,
                (
                    singleton(address(a)),
                    0,
                    block.timestamp + 1 days
                )
            )
        );
        require(!ok, "zero-payment offer accepted");
    }

    function testDuplicateTargetRejected() public {
        (AtomicBypassEscrow escrow,) = deploy(2, 1);
        Receiver a = new Receiver();
        (bool ok,) = address(escrow).call{value: 2 wei}(
            abi.encodeCall(
                escrow.createOffer,
                (
                    pair(address(a), address(a)),
                    1 wei,
                    block.timestamp + 1 days
                )
            )
        );
        require(!ok, "duplicate target accepted");
    }

    function testInvalidShareRejected() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(1, 1);
        Receiver a = new Receiver();
        uint256 offerId = escrow.createOffer{value: 1 wei}(
            singleton(address(a)),
            1 wei,
            block.timestamp + 1 days
        );
        (bool invalidOk,) = address(a).call(
            abi.encodeCall(a.accept, (escrow, offerId, bytes(hex"01")))
        );
        require(!invalidOk, "unverified share accepted");
        authorize(verifier, offerId, address(a), hex"01");
        a.accept(escrow, offerId, hex"01");
        require(escrow.accepted(offerId, address(a)), "valid share rejected");
    }

    function testRevertingMemberPreservesAtomicity() public {
        (
            AtomicBypassEscrow escrow,
            MockShareVerifier verifier
        ) = deploy(2, 1);
        Receiver good = new Receiver();
        RejectingReceiver bad = new RejectingReceiver();
        uint256 offerId = escrow.createOffer{value: 2 wei}(
            pair(address(good), address(bad)),
            1 wei,
            block.timestamp + 1 days
        );
        authorize(verifier, offerId, address(good), hex"01");
        authorize(verifier, offerId, address(bad), hex"02");
        good.accept(escrow, offerId, hex"01");
        bad.accept(escrow, offerId, hex"02");
        (bool ok,) = address(escrow).call(
            abi.encodeCall(escrow.settle, (offerId))
        );
        require(!ok, "reverting payment did not revert settlement");
        require(address(good).balance == 0, "partial payment escaped");
        require(address(bad).balance == 0, "bad receiver was paid");
        require(address(escrow).balance == 2 wei, "escrow was not restored");
    }

    function testExpiredOfferRefundAndAccessControl() public {
        (AtomicBypassEscrow escrow,) = deploy(1, 1);
        Receiver a = new Receiver();
        Receiver outsider = new Receiver();
        uint256 startingBalance = address(this).balance;
        uint256 deadline = block.timestamp + 1;
        uint256 offerId = escrow.createOffer{value: 1 wei}(
            singleton(address(a)),
            1 wei,
            deadline
        );
        vm.warp(deadline + 1);
        (bool outsiderOk,) = address(outsider).call(
            abi.encodeCall(outsider.refund, (escrow, offerId))
        );
        require(!outsiderOk, "outsider refunded offer");
        escrow.refundExpired(offerId);
        require(address(this).balance == startingBalance, "buyer not refunded");
        require(address(escrow).balance == 0, "escrow retained refund");
    }

    function testZeroVerifierRejected() public {
        try new AtomicBypassEscrow(1, 1, IShareVerifier(address(0))) returns (
            AtomicBypassEscrow deployed
        ) {
            require(address(deployed) == address(0), "zero verifier accepted");
            revert("zero verifier accepted");
        } catch {}
    }
}
