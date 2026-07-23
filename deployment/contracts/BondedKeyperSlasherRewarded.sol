// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Research pilot for evidence-gated slashing of premature Shutter key shares,
///         with a caller-reward split so that enforcement is rational for an
///         unsubsidized caller, not merely mechanically executable.
/// @dev This is a parallel, additive contract: `BondedKeyperSlasher.sol` (this
///      file's un-rewarded predecessor) remains unmodified because its exact
///      source hash is bound into the already-recorded, already-executed
///      `certificates/chiado-execution-certificate.json`. Changing that file
///      in place would silently invalidate a real prior on-chain run's
///      certificate. This file is a separate, not-yet-deployed design.
/// @dev BLS share validity and the native Keyper signature are checked off chain by
///      the pinned evidence verifier. The contract verifies the verifier's EIP-712
///      attestation and enforces the release deadline and bond transfer on chain.
contract BondedKeyperSlasherRewarded is EIP712, Ownable, ReentrancyGuard {
    uint8 public constant COMMITTEE_SIZE = 7;
    uint8 public constant THRESHOLD = 4;

    bytes32 public constant EARLY_SHARE_TYPEHASH = keccak256(
        "EarlyShareEvidence(bytes32 jobId,uint8 memberIndex,bytes32 shareHash,bytes32 memberSignatureHash)"
    );

    struct Member {
        address signer;
        uint96 bond;
        bool registered;
        bool slashed;
    }

    struct ReleaseJob {
        uint64 eon;
        uint64 releaseTime;
        bytes32 identityHash;
        bool exists;
    }

    Member[COMMITTEE_SIZE] public members;
    mapping(address => bool) public signerRegistered;
    mapping(bytes32 => ReleaseJob) public jobs;
    mapping(bytes32 => bool) public usedEvidence;

    address public immutable verifier;
    address payable public immutable treasury;
    /// @notice Paid to whoever submits a valid slashing transaction, out of the
    ///         forfeited bond itself, so that enforcement is not merely
    ///         mechanically executable but rational for an unsubsidized caller
    ///         to actually perform. Sized against the worst-case observed gas
    ///         cost of `slashEarlyShare` (see
    ///         `scripts/report_slashing_reward_ratio.py`), not an arbitrary
    ///         nominal amount.
    uint256 public immutable callerRewardWei;
    bool public committeeFrozen;
    uint8 public registeredCount;
    uint64 public jobCount;

    event MemberRegistered(uint8 indexed memberIndex, address indexed signer, uint256 bond);
    event CommitteeFrozen(uint8 memberCount, uint8 threshold, uint256 totalBond, uint256 certificate);
    event ReleaseOpened(
        bytes32 indexed jobId,
        uint64 indexed eon,
        bytes32 indexed identityHash,
        uint64 releaseTime
    );
    event EarlyShareSlashed(
        bytes32 indexed jobId,
        uint8 indexed memberIndex,
        bytes32 indexed shareHash,
        bytes32 memberSignatureHash,
        uint64 observedAt,
        uint256 amount,
        address caller,
        uint256 callerReward,
        uint256 treasuryAmount
    );

    error InvalidAddress();
    error InvalidMemberIndex();
    error InvalidBond();
    error InvalidCallerReward();
    error AlreadyRegistered();
    error DuplicateSigner();
    error CommitteeAlreadyFrozen();
    error CommitteeNotFrozen();
    error CommitteeIncomplete();
    error InvalidReleaseTime();
    error UnknownJob();
    error ReleaseWindowClosed();
    error AlreadySlashed();
    error EvidenceAlreadyUsed();
    error InvalidVerifierSignature();
    error TreasuryTransferFailed();
    error CallerRewardTransferFailed();
    error SelfSlashNotAllowed();

    constructor(
        address initialOwner,
        address evidenceVerifier,
        address payable penaltyTreasury,
        uint256 callerRewardWei_
    )
        EIP712("BondedKeyperSlasherRewarded", "1")
        Ownable(initialOwner)
    {
        if (evidenceVerifier == address(0) || penaltyTreasury == address(0)) revert InvalidAddress();
        if (callerRewardWei_ == 0) revert InvalidCallerReward();
        verifier = evidenceVerifier;
        treasury = penaltyTreasury;
        callerRewardWei = callerRewardWei_;
    }

    function registerMember(uint8 memberIndex, address signer) external payable onlyOwner {
        if (committeeFrozen) revert CommitteeAlreadyFrozen();
        if (memberIndex >= COMMITTEE_SIZE) revert InvalidMemberIndex();
        if (signer == address(0)) revert InvalidAddress();
        if (msg.value <= callerRewardWei || msg.value > type(uint96).max) revert InvalidBond();

        Member storage member = members[memberIndex];
        if (member.registered) revert AlreadyRegistered();
        if (signerRegistered[signer]) revert DuplicateSigner();
        member.signer = signer;
        member.bond = uint96(msg.value);
        member.registered = true;
        signerRegistered[signer] = true;
        registeredCount += 1;

        emit MemberRegistered(memberIndex, signer, msg.value);
    }

    function freezeCommittee() external onlyOwner {
        if (committeeFrozen) revert CommitteeAlreadyFrozen();
        if (registeredCount != COMMITTEE_SIZE) revert CommitteeIncomplete();
        committeeFrozen = true;
        emit CommitteeFrozen(COMMITTEE_SIZE, THRESHOLD, totalBond(), currentCertificate());
    }

    function computeJobId(
        uint64 eon,
        bytes32 identityHash,
        uint64 releaseTime,
        uint64 nonce
    ) public view returns (bytes32) {
        return keccak256(abi.encode(block.chainid, address(this), eon, identityHash, releaseTime, nonce));
    }

    function openRelease(
        uint64 eon,
        bytes32 identityHash,
        uint64 releaseTime
    ) external onlyOwner returns (bytes32 jobId) {
        if (!committeeFrozen) revert CommitteeNotFrozen();
        if (releaseTime <= block.timestamp) revert InvalidReleaseTime();
        uint64 nonce = ++jobCount;
        jobId = computeJobId(eon, identityHash, releaseTime, nonce);
        jobs[jobId] = ReleaseJob({
            eon: eon,
            releaseTime: releaseTime,
            identityHash: identityHash,
            exists: true
        });
        emit ReleaseOpened(jobId, eon, identityHash, releaseTime);
    }

    function evidenceDigest(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes32 memberSignatureHash
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(EARLY_SHARE_TYPEHASH, jobId, memberIndex, shareHash, memberSignatureHash)
        );
        return _hashTypedDataV4(structHash);
    }

    function slashEarlyShare(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes32 memberSignatureHash,
        bytes calldata verifierSignature
    ) external nonReentrant {
        if (memberIndex >= COMMITTEE_SIZE) revert InvalidMemberIndex();
        ReleaseJob memory job = jobs[jobId];
        if (!job.exists) revert UnknownJob();
        if (block.timestamp >= job.releaseTime) revert ReleaseWindowClosed();

        Member storage member = members[memberIndex];
        if (member.slashed || member.bond == 0) revert AlreadySlashed();
        if (msg.sender == member.signer) revert SelfSlashNotAllowed();

        bytes32 digest = evidenceDigest(jobId, memberIndex, shareHash, memberSignatureHash);
        if (usedEvidence[digest]) revert EvidenceAlreadyUsed();
        if (ECDSA.recover(digest, verifierSignature) != verifier) {
            revert InvalidVerifierSignature();
        }
        usedEvidence[digest] = true;

        uint256 amount = member.bond;
        member.bond = 0;
        member.slashed = true;

        uint256 callerReward = callerRewardWei;
        uint256 treasuryAmount = amount - callerReward;

        (bool rewardSent,) = payable(msg.sender).call{value: callerReward}("");
        if (!rewardSent) revert CallerRewardTransferFailed();

        (bool sent,) = treasury.call{value: treasuryAmount}("");
        if (!sent) revert TreasuryTransferFailed();

        emit EarlyShareSlashed(
            jobId,
            memberIndex,
            shareHash,
            memberSignatureHash,
            uint64(block.timestamp),
            amount,
            msg.sender,
            callerReward,
            treasuryAmount
        );
    }

    function totalBond() public view returns (uint256 total) {
        for (uint8 i = 0; i < COMMITTEE_SIZE; ++i) {
            total += members[i].bond;
        }
    }

    /// @notice Sum of the four smallest live bonds for the uniform 4-of-7 pilot.
    function currentCertificate() public view returns (uint256 certificate) {
        uint256[COMMITTEE_SIZE] memory bonds;
        for (uint8 i = 0; i < COMMITTEE_SIZE; ++i) {
            bonds[i] = members[i].bond;
        }
        for (uint8 i = 1; i < COMMITTEE_SIZE; ++i) {
            uint256 value = bonds[i];
            uint8 j = i;
            while (j > 0 && bonds[j - 1] > value) {
                bonds[j] = bonds[j - 1];
                --j;
            }
            bonds[j] = value;
        }
        for (uint8 i = 0; i < THRESHOLD; ++i) {
            certificate += bonds[i];
        }
    }
}
