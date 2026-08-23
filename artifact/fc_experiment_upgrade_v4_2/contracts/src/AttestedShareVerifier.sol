// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./AtomicBypassEscrow.sol";

/// @notice Verifies an attestation produced after native Rolling Shutter checks.
/// @dev The attester is responsible for verifying the threshold share equation,
///      the member's native signature, and the epoch/DKG binding off chain.
contract AttestedShareVerifier is IShareVerifier {
    bytes32 public constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 public constant SHARE_ATTESTATION_TYPEHASH = keccak256(
        "ShareAttestation(address escrow,uint256 offerId,address member,bytes32 shareHash)"
    );
    bytes32 public constant NAME_HASH = keccak256("FC Attested Share Verifier");
    bytes32 public constant VERSION_HASH = keccak256("1");
    uint256 private constant SECP256K1N_HALF =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    address public immutable attester;

    constructor(address attester_) {
        require(attester_ != address(0), "zero attester");
        attester = attester_;
    }

    function domainSeparator() public view returns (bytes32) {
        return keccak256(
            abi.encode(
                DOMAIN_TYPEHASH,
                NAME_HASH,
                VERSION_HASH,
                block.chainid,
                address(this)
            )
        );
    }

    function attestationDigest(
        address escrow,
        uint256 offerId,
        address member,
        bytes32 shareHash
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                SHARE_ATTESTATION_TYPEHASH,
                escrow,
                offerId,
                member,
                shareHash
            )
        );
        return keccak256(
            abi.encodePacked("\x19\x01", domainSeparator(), structHash)
        );
    }

    function verifyShare(
        uint256 offerId,
        address member,
        bytes calldata share,
        bytes calldata proof
    ) external view returns (bool) {
        if (member == address(0) || share.length == 0 || proof.length != 65) {
            return false;
        }

        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(proof.offset)
            s := calldataload(add(proof.offset, 32))
            v := byte(0, calldataload(add(proof.offset, 64)))
        }
        if (v != 27 && v != 28) {
            return false;
        }
        if (uint256(s) > SECP256K1N_HALF) {
            return false;
        }

        bytes32 digest = attestationDigest(
            msg.sender,
            offerId,
            member,
            keccak256(share)
        );
        address recovered = ecrecover(digest, v, r, s);
        return recovered != address(0) && recovered == attester;
    }
}
