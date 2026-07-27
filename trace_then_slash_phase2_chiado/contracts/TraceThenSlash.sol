// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @notice Phase-one Trace-Then-Slash mechanism for a fixed 4-of-7 committee.
/// @dev Each covered early-share artifact carries both the bonded member's
///      accountability signature and a verifier attestation of share validity.
///      Slashing accrues a non-zero caller reward without making enforcement
///      depend on an external recipient accepting ETH during the slash call.
contract TraceThenSlash is EIP712, Ownable, ReentrancyGuard {
    uint8 public constant COMMITTEE_SIZE = 7;
    uint8 public constant THRESHOLD = 4;

    bytes32 public constant EARLY_SHARE_ARTIFACT_TYPEHASH = keccak256(
        "EarlyShareArtifact(bytes32 jobId,uint8 memberIndex,bytes32 shareHash)"
    );
    bytes32 public constant EARLY_SHARE_EVIDENCE_TYPEHASH = keccak256(
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
    mapping(address => uint256) public claimableRewards;

    address public immutable verifier;
    address public immutable treasury;
    uint96 public immutable callerRewardPerSlash;

    bool public committeeFrozen;
    uint8 public registeredCount;
    uint64 public jobCount;
    uint256 public frozenThresholdBondFloor;
    uint256 public treasuryAccrued;

    event MemberRegistered(uint8 indexed memberIndex, address indexed signer, uint256 bond);
    event CommitteeFrozen(
        uint8 memberCount,
        uint8 threshold,
        uint256 totalBond,
        uint256 thresholdBondFloor
    );
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
        bytes32 evidenceDigest,
        uint256 memberLoss,
        uint256 callerReward,
        uint256 treasuryAccrual
    );
    event PackageSlashed(
        bytes32 indexed jobId,
        bytes32 indexed packageId,
        address indexed caller,
        uint256 evidenceCount,
        uint256 totalMemberLoss,
        uint256 totalCallerReward,
        uint256 totalTreasuryAccrual,
        uint256 certificateBefore,
        uint256 certificateAfter
    );
    event RewardWithdrawn(address indexed caller, address indexed recipient, uint256 amount);
    event TreasuryWithdrawn(address indexed recipient, uint256 amount);

    error InvalidAddress();
    error InvalidMemberIndex();
    error InvalidBond();
    error InvalidReward();
    error AlreadyRegistered();
    error DuplicateSigner();
    error CommitteeAlreadyFrozen();
    error CommitteeNotFrozen();
    error CommitteeIncomplete();
    error InvalidReleaseTime();
    error UnknownJob();
    error MixedJobs();
    error ReleaseWindowClosed();
    error AlreadySlashed();
    error EmptyEvidence();
    error InvalidEvidence();
    error EvidenceAlreadyUsed();
    error InvalidMemberSignature();
    error InvalidVerifierSignature();
    error InvalidPackageLength();
    error DuplicateMemberInPackage();
    error MemberCallerForbidden();
    error NothingToWithdraw();
    error UnauthorizedTreasury();
    error TransferFailed();

    constructor(
        address initialOwner,
        address evidenceVerifier,
        address penaltyTreasury,
        uint96 perSlashCallerReward
    ) EIP712("TraceThenSlash", "1") Ownable(initialOwner) {
        if (
            initialOwner == address(0) ||
            evidenceVerifier == address(0) ||
            penaltyTreasury == address(0)
        ) revert InvalidAddress();
        if (perSlashCallerReward == 0) revert InvalidReward();
        verifier = evidenceVerifier;
        treasury = penaltyTreasury;
        callerRewardPerSlash = perSlashCallerReward;
    }

    function registerMember(uint8 memberIndex, address signer) external payable onlyOwner {
        if (committeeFrozen) revert CommitteeAlreadyFrozen();
        if (memberIndex >= COMMITTEE_SIZE) revert InvalidMemberIndex();
        if (signer == address(0)) revert InvalidAddress();
        if (msg.value <= callerRewardPerSlash || msg.value > type(uint96).max) {
            revert InvalidBond();
        }

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
        frozenThresholdBondFloor = currentCertificate();
        emit CommitteeFrozen(
            COMMITTEE_SIZE,
            THRESHOLD,
            totalBond(),
            frozenThresholdBondFloor
        );
    }

    function computeJobId(
        uint64 eon,
        bytes32 identityHash,
        uint64 releaseTime,
        uint64 nonce
    ) public view returns (bytes32) {
        return keccak256(
            abi.encode(block.chainid, address(this), eon, identityHash, releaseTime, nonce)
        );
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

    function artifactDigest(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(EARLY_SHARE_ARTIFACT_TYPEHASH, jobId, memberIndex, shareHash)
        );
        return _hashTypedDataV4(structHash);
    }

    function evidenceDigest(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes32 memberSignatureHash
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                EARLY_SHARE_EVIDENCE_TYPEHASH,
                jobId,
                memberIndex,
                shareHash,
                memberSignatureHash
            )
        );
        return _hashTypedDataV4(structHash);
    }

    function slashEarlyShare(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes calldata memberSignature,
        bytes calldata verifierSignature
    ) external nonReentrant {
        if (signerRegistered[msg.sender]) revert MemberCallerForbidden();
        uint256 certificateBefore = currentCertificate();
        (bytes32 digest, uint256 memberLoss) = _validateEvidence(
            jobId,
            memberIndex,
            shareHash,
            memberSignature,
            verifierSignature
        );

        _applySlash(jobId, memberIndex, shareHash, digest, memberLoss, msg.sender);
        bytes32 packageId = keccak256(abi.encode(digest));
        emit PackageSlashed(
            jobId,
            packageId,
            msg.sender,
            1,
            memberLoss,
            callerRewardPerSlash,
            memberLoss - callerRewardPerSlash,
            certificateBefore,
            currentCertificate()
        );
    }

    /// @notice Atomically validates and slashes 1..7 distinct members for one job.
    /// @dev The first pass validates the entire package. Any invalid member,
    ///      signature, duplicate, or stale job reverts before state is changed.
    function slashPackage(
        bytes32[] calldata jobIds,
        uint8[] calldata memberIndices,
        bytes32[] calldata shareHashes,
        bytes[] calldata memberSignatures,
        bytes[] calldata verifierSignatures
    ) external nonReentrant {
        if (signerRegistered[msg.sender]) revert MemberCallerForbidden();
        uint256 count = jobIds.length;
        if (
            count == 0 ||
            count > COMMITTEE_SIZE ||
            memberIndices.length != count ||
            shareHashes.length != count ||
            memberSignatures.length != count ||
            verifierSignatures.length != count
        ) revert InvalidPackageLength();

        bytes32 packageJobId = jobIds[0];
        bytes32[] memory digests = new bytes32[](count);
        uint256[] memory losses = new uint256[](count);
        uint256 totalMemberLoss;

        for (uint256 i = 0; i < count; ++i) {
            if (jobIds[i] != packageJobId) revert MixedJobs();
            for (uint256 j = 0; j < i; ++j) {
                if (memberIndices[j] == memberIndices[i]) {
                    revert DuplicateMemberInPackage();
                }
            }
            (digests[i], losses[i]) = _validateEvidence(
                jobIds[i],
                memberIndices[i],
                shareHashes[i],
                memberSignatures[i],
                verifierSignatures[i]
            );
            totalMemberLoss += losses[i];
        }

        uint256 certificateBefore = currentCertificate();
        bytes32 packageId;
        for (uint256 i = 0; i < count; ++i) {
            packageId = keccak256(abi.encode(packageId, digests[i]));
            _applySlash(
                jobIds[i],
                memberIndices[i],
                shareHashes[i],
                digests[i],
                losses[i],
                msg.sender
            );
        }

        uint256 totalCallerReward = count * callerRewardPerSlash;
        emit PackageSlashed(
            packageJobId,
            packageId,
            msg.sender,
            count,
            totalMemberLoss,
            totalCallerReward,
            totalMemberLoss - totalCallerReward,
            certificateBefore,
            currentCertificate()
        );
    }

    function withdrawReward(address payable recipient) external nonReentrant {
        if (recipient == address(0)) revert InvalidAddress();
        uint256 amount = claimableRewards[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        claimableRewards[msg.sender] = 0;
        (bool sent,) = recipient.call{value: amount}("");
        if (!sent) revert TransferFailed();
        emit RewardWithdrawn(msg.sender, recipient, amount);
    }

    function withdrawTreasury(address payable recipient) external nonReentrant {
        if (msg.sender != treasury) revert UnauthorizedTreasury();
        if (recipient == address(0)) revert InvalidAddress();
        uint256 amount = treasuryAccrued;
        if (amount == 0) revert NothingToWithdraw();
        treasuryAccrued = 0;
        (bool sent,) = recipient.call{value: amount}("");
        if (!sent) revert TransferFailed();
        emit TreasuryWithdrawn(recipient, amount);
    }

    function _validateEvidence(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes calldata memberSignature,
        bytes calldata verifierSignature
    ) internal view returns (bytes32 digest, uint256 memberLoss) {
        if (memberIndex >= COMMITTEE_SIZE) revert InvalidMemberIndex();
        if (shareHash == bytes32(0)) revert InvalidEvidence();

        ReleaseJob memory job = jobs[jobId];
        if (!job.exists) revert UnknownJob();
        if (block.timestamp >= job.releaseTime) revert ReleaseWindowClosed();

        Member storage member = members[memberIndex];
        if (member.slashed || member.bond == 0) revert AlreadySlashed();
        if (
            ECDSA.recover(
                artifactDigest(jobId, memberIndex, shareHash),
                memberSignature
            ) != member.signer
        ) revert InvalidMemberSignature();

        bytes32 memberSignatureHash = keccak256(memberSignature);
        digest = evidenceDigest(jobId, memberIndex, shareHash, memberSignatureHash);
        if (usedEvidence[digest]) revert EvidenceAlreadyUsed();
        if (ECDSA.recover(digest, verifierSignature) != verifier) {
            revert InvalidVerifierSignature();
        }
        memberLoss = member.bond;
    }

    function _applySlash(
        bytes32 jobId,
        uint8 memberIndex,
        bytes32 shareHash,
        bytes32 digest,
        uint256 memberLoss,
        address caller
    ) internal {
        Member storage member = members[memberIndex];
        usedEvidence[digest] = true;
        member.bond = 0;
        member.slashed = true;

        uint256 reward = callerRewardPerSlash;
        uint256 treasuryAmount = memberLoss - reward;
        claimableRewards[caller] += reward;
        treasuryAccrued += treasuryAmount;

        emit EarlyShareSlashed(
            jobId,
            memberIndex,
            shareHash,
            digest,
            memberLoss,
            reward,
            treasuryAmount
        );
    }

    function totalBond() public view returns (uint256 total) {
        for (uint8 i = 0; i < COMMITTEE_SIZE; ++i) {
            total += members[i].bond;
        }
    }

    /// @notice Sum of the four smallest currently live bonds.
    /// @dev After threshold slashing this becomes zero; that is loss of ongoing
    ///      committee security, not a zero pre-attack cost certificate.
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
