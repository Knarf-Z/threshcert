// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/AtomicBypassEscrow.sol";
import "../src/AttestedShareVerifier.sol";

interface AttestedVm {
    function addr(uint256 privateKey) external returns (address);
    function sign(
        uint256 privateKey,
        bytes32 digest
    ) external returns (uint8 v, bytes32 r, bytes32 s);
}

contract AttestedReceiver {
    function accept(
        AtomicBypassEscrow escrow,
        uint256 offerId,
        bytes calldata share,
        bytes calldata proof
    ) external {
        escrow.accept(offerId, share, proof);
    }

    receive() external payable {}
}

contract AttestedShareVerifierTest {
    AttestedVm private constant vm =
        AttestedVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    uint256 private constant ATTESTER_PRIVATE_KEY = 0xA11CE;

    receive() external payable {}

    function singleton(
        address member
    ) internal pure returns (address[] memory members) {
        members = new address[](1);
        members[0] = member;
    }

    function deployAttested(
        uint256 invocationLimit
    ) internal returns (
        AtomicBypassEscrow escrow,
        AttestedShareVerifier verifier
    ) {
        verifier = new AttestedShareVerifier(
            vm.addr(ATTESTER_PRIVATE_KEY)
        );
        escrow = new AtomicBypassEscrow(2, invocationLimit, verifier);
    }

    function signedProof(
        AttestedShareVerifier verifier,
        AtomicBypassEscrow escrow,
        uint256 offerId,
        address member,
        bytes memory share,
        uint256 privateKey
    ) internal returns (bytes memory) {
        bytes32 digest = verifier.attestationDigest(
            address(escrow),
            offerId,
            member,
            keccak256(share)
        );
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function create(
        AtomicBypassEscrow escrow,
        AttestedReceiver member
    ) internal returns (uint256) {
        return escrow.createOffer{value: 1 wei}(
            singleton(address(member)),
            1 wei,
            block.timestamp + 1 days
        );
    }

    function testAttestedShareAccepted() public {
        (
            AtomicBypassEscrow escrow,
            AttestedShareVerifier verifier
        ) = deployAttested(1);
        AttestedReceiver member = new AttestedReceiver();
        uint256 offerId = create(escrow, member);
        bytes memory share = hex"aabb";
        bytes memory proof = signedProof(
            verifier,
            escrow,
            offerId,
            address(member),
            share,
            ATTESTER_PRIVATE_KEY
        );
        member.accept(escrow, offerId, share, proof);
        require(
            escrow.accepted(offerId, address(member)),
            "attested share rejected"
        );
    }

    function testAttestationBindsShareHash() public {
        (
            AtomicBypassEscrow escrow,
            AttestedShareVerifier verifier
        ) = deployAttested(1);
        AttestedReceiver member = new AttestedReceiver();
        uint256 offerId = create(escrow, member);
        bytes memory proof = signedProof(
            verifier,
            escrow,
            offerId,
            address(member),
            hex"aabb",
            ATTESTER_PRIVATE_KEY
        );
        (bool ok,) = address(member).call(
            abi.encodeCall(
                member.accept,
                (escrow, offerId, bytes(hex"aabc"), proof)
            )
        );
        require(!ok, "proof replayed for another share");
    }

    function testAttestationBindsMember() public {
        (
            AtomicBypassEscrow escrow,
            AttestedShareVerifier verifier
        ) = deployAttested(1);
        AttestedReceiver member = new AttestedReceiver();
        AttestedReceiver other = new AttestedReceiver();
        uint256 offerId = create(escrow, member);
        bytes memory share = hex"aabb";
        bytes memory proof = signedProof(
            verifier,
            escrow,
            offerId,
            address(other),
            share,
            ATTESTER_PRIVATE_KEY
        );
        (bool ok,) = address(member).call(
            abi.encodeCall(
                member.accept,
                (escrow, offerId, share, proof)
            )
        );
        require(!ok, "proof replayed for another member");
    }

    function testAttestationBindsOffer() public {
        (
            AtomicBypassEscrow escrow,
            AttestedShareVerifier verifier
        ) = deployAttested(2);
        AttestedReceiver member = new AttestedReceiver();
        uint256 first = create(escrow, member);
        uint256 second = create(escrow, member);
        bytes memory share = hex"aabb";
        bytes memory proof = signedProof(
            verifier,
            escrow,
            first,
            address(member),
            share,
            ATTESTER_PRIVATE_KEY
        );
        (bool ok,) = address(member).call(
            abi.encodeCall(
                member.accept,
                (escrow, second, share, proof)
            )
        );
        require(!ok, "proof replayed across offers");
    }

    function testAttestationBindsEscrow() public {
        (
            AtomicBypassEscrow firstEscrow,
            AttestedShareVerifier verifier
        ) = deployAttested(1);
        AtomicBypassEscrow secondEscrow = new AtomicBypassEscrow(
            2,
            1,
            verifier
        );
        AttestedReceiver member = new AttestedReceiver();
        uint256 firstOffer = create(firstEscrow, member);
        uint256 secondOffer = create(secondEscrow, member);
        require(firstOffer == secondOffer, "fixture offer IDs differ");
        bytes memory share = hex"aabb";
        bytes memory proof = signedProof(
            verifier,
            firstEscrow,
            firstOffer,
            address(member),
            share,
            ATTESTER_PRIVATE_KEY
        );
        (bool ok,) = address(member).call(
            abi.encodeCall(
                member.accept,
                (secondEscrow, secondOffer, share, proof)
            )
        );
        require(!ok, "proof replayed across escrows");
    }

    function testAttestationRejectsWrongSigner() public {
        (
            AtomicBypassEscrow escrow,
            AttestedShareVerifier verifier
        ) = deployAttested(1);
        AttestedReceiver member = new AttestedReceiver();
        uint256 offerId = create(escrow, member);
        bytes memory share = hex"aabb";
        bytes memory proof = signedProof(
            verifier,
            escrow,
            offerId,
            address(member),
            share,
            ATTESTER_PRIVATE_KEY + 1
        );
        (bool ok,) = address(member).call(
            abi.encodeCall(
                member.accept,
                (escrow, offerId, share, proof)
            )
        );
        require(!ok, "untrusted attester accepted");
    }
}
