// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Controlled 4-of-7 residual-price fixture for the paper's
/// overlapping-pool instance. It certifies contract-recognized credits,
/// transfers four unique on-chain share rights, and closes endogenous value
/// provenance: credits enter only from a role-separated pool controller, while
/// exact acquisition value enters from a nonmember, noncontroller acquirer who
/// has no withdrawal or refund path. Off-contract beneficial ownership and the
/// binding from a share right to usable cryptographic material remain outside
/// this controlled-runtime claim.
contract OverlappingPoolEscrow {
    uint256 public constant CREDIT_UNIT = 1 ether;
    uint256 public constant MEMBER_GROSS_FLOOR = 2 ether;
    uint256 public constant POOL_CAP = 2 ether;
    uint256 public constant COMMITTEE_SIZE = 7;
    uint256 public constant THRESHOLD = 4;

    address public immutable poolController;
    address[7] public members;
    uint256[7] public credits;
    /// @notice Owner of each unique controlled share right.
    address[7] public shareOwner;

    bool public configured;
    bool public completed;
    uint8 public terminalMask;
    uint8 public deliveredShareMask;
    uint256 public totalAcquisitionCallValue;
    /// @notice Immediate successful acquireFour caller; not funding provenance.
    address public acquirer;
    bool private entered;

    mapping(address member => uint256 amount) public claimable;

    event CreditsConfigured(
        uint256 totalCredits,
        uint256 firstPoolUsage,
        uint256 secondPoolUsage
    );
    event AcquisitionRecorded(
        address indexed acquirer,
        uint256 indexed memberIndex,
        address indexed member,
        uint256 poolCredit,
        uint256 directCallValue
    );
    event ShareRightDelivered(
        uint256 indexed memberIndex,
        address indexed previousOwner,
        address indexed acquirer
    );
    event Withdrawn(address indexed member, uint256 amount);

    error AlreadyConfigured();
    error AlreadyCompleted();
    error ConflictingRole();
    error DuplicateMember();
    error IncorrectFunding();
    error InvalidMember();
    error InvalidMemberSet();
    error InvalidPoolState();
    error InvalidShareState();
    error NotConfigured();
    error NotExternalAcquirer();
    error NotPoolController();
    error NothingToWithdraw();
    error TransferFailed();
    error Reentrancy();

    modifier nonReentrant() {
        if (entered) revert Reentrancy();
        entered = true;
        _;
        entered = false;
    }

    constructor(address controller, address[7] memory committee) {
        if (controller == address(0)) revert InvalidMember();
        poolController = controller;

        for (uint256 i = 0; i < COMMITTEE_SIZE; i++) {
            if (committee[i] == address(0)) revert InvalidMember();
            if (committee[i] == controller) revert ConflictingRole();
            for (uint256 j = 0; j < i; j++) {
                if (committee[i] == committee[j]) revert DuplicateMember();
            }
            members[i] = committee[i];
            shareOwner[i] = committee[i];
        }
    }

    function configureCredits(uint256[7] calldata candidate)
        external
        payable
        nonReentrant
    {
        if (msg.sender != poolController) revert NotPoolController();
        if (configured) revert AlreadyConfigured();

        (
            uint256 totalCredits,
            uint256 firstPoolUsage,
            uint256 secondPoolUsage
        ) = _validateCredits(candidate);
        if (msg.value != totalCredits) revert IncorrectFunding();

        configured = true;
        for (uint256 i = 0; i < COMMITTEE_SIZE; i++) {
            credits[i] = candidate[i];
            claimable[members[i]] += candidate[i];
        }

        emit CreditsConfigured(
            totalCredits,
            firstPoolUsage,
            secondPoolUsage
        );
    }

    function residualPrice(uint256 memberIndex) public view returns (uint256) {
        if (!configured) revert NotConfigured();
        if (memberIndex >= COMMITTEE_SIZE) revert InvalidMember();
        return MEMBER_GROSS_FLOOR - credits[memberIndex];
    }

    function quoteFour(uint8[4] calldata memberIndices)
        public
        view
        returns (uint256 total)
    {
        if (!configured) revert NotConfigured();
        _validateMemberSet(memberIndices);

        for (uint256 i = 0; i < THRESHOLD; i++) {
            total += residualPrice(memberIndices[i]);
        }
    }

    function quoteCandidate(
        uint256[7] calldata candidate,
        uint8[4] calldata memberIndices
    ) external pure returns (uint256 total) {
        _validateCredits(candidate);
        _validateMemberSet(memberIndices);

        for (uint256 i = 0; i < THRESHOLD; i++) {
            total += MEMBER_GROSS_FLOOR - candidate[memberIndices[i]];
        }
    }

    function acquireFour(uint8[4] calldata memberIndices)
        external
        payable
        nonReentrant
    {
        if (!configured) revert NotConfigured();
        if (completed) revert AlreadyCompleted();
        if (!_isExternalAcquirer(msg.sender)) revert NotExternalAcquirer();

        uint256 requiredPayment = quoteFour(memberIndices);
        if (msg.value != requiredPayment) revert IncorrectFunding();

        uint8 mask;

        for (uint256 i = 0; i < THRESHOLD; i++) {
            uint256 memberIndex = memberIndices[i];
            // memberIndex is validated in [0,6], so the cast is exact.
            // forge-lint: disable-next-line(unsafe-typecast)
            mask |= uint8(2 ** memberIndex);
            uint256 directPayment =
                MEMBER_GROSS_FLOOR - credits[memberIndex];
            address member = members[memberIndex];
            address previousOwner = shareOwner[memberIndex];
            if (previousOwner != member) revert InvalidShareState();
            shareOwner[memberIndex] = msg.sender;
            claimable[member] += directPayment;
            emit ShareRightDelivered(
                memberIndex,
                previousOwner,
                msg.sender
            );
            emit AcquisitionRecorded(
                msg.sender,
                memberIndex,
                member,
                credits[memberIndex],
                directPayment
            );
        }

        terminalMask = mask;
        deliveredShareMask = mask;
        completed = true;
        totalAcquisitionCallValue = requiredPayment;
        acquirer = msg.sender;
    }

    function withdraw() external nonReentrant {
        uint256 amount = claimable[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        claimable[msg.sender] = 0;

        (bool success,) = payable(msg.sender).call{value: amount}("");
        if (!success) revert TransferFailed();
        emit Withdrawn(msg.sender, amount);
    }

    function _isExternalAcquirer(address candidate)
        internal
        view
        returns (bool)
    {
        if (candidate == poolController) return false;
        for (uint256 i = 0; i < COMMITTEE_SIZE; i++) {
            if (candidate == members[i]) return false;
        }
        return true;
    }

    function _validateCredits(uint256[7] calldata candidate)
        internal
        pure
        returns (
            uint256 totalCredits,
            uint256 firstPoolUsage,
            uint256 secondPoolUsage
        )
    {
        for (uint256 i = 0; i < COMMITTEE_SIZE; i++) {
            uint256 credit = candidate[i];
            if (
                credit > MEMBER_GROSS_FLOOR ||
                credit % CREDIT_UNIT != 0
            ) revert InvalidPoolState();
            totalCredits += credit;
            if (i <= 3) firstPoolUsage += credit;
            if (i >= 3) secondPoolUsage += credit;
        }
        if (firstPoolUsage > POOL_CAP || secondPoolUsage > POOL_CAP) {
            revert InvalidPoolState();
        }
    }

    function _validateMemberSet(uint8[4] calldata memberIndices)
        internal
        pure
    {
        for (uint256 i = 0; i < THRESHOLD; i++) {
            if (memberIndices[i] >= COMMITTEE_SIZE) {
                revert InvalidMemberSet();
            }
            if (i > 0 && memberIndices[i] <= memberIndices[i - 1]) {
                revert InvalidMemberSet();
            }
        }
    }
}
