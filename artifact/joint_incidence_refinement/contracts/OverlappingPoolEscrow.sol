// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Controlled 4-of-7 residual-price fixture for the paper's
/// overlapping-pool instance. It certifies contract-recognized credits and
/// direct attacker payment only; ultimate beneficial ownership remains a
/// separately declared provenance assumption.
contract OverlappingPoolEscrow {
    uint256 public constant CREDIT_UNIT = 1 ether;
    uint256 public constant MEMBER_GROSS_FLOOR = 2 ether;
    uint256 public constant POOL_CAP = 2 ether;
    uint256 public constant COMMITTEE_SIZE = 7;
    uint256 public constant THRESHOLD = 4;

    address public immutable poolController;
    address[7] public members;
    uint256[7] public credits;

    bool public configured;
    bool public completed;
    uint256 public totalAttackerPayment;

    mapping(address member => uint256 amount) public claimable;

    event CreditsConfigured(
        uint256 totalCredits,
        uint256 firstPoolUsage,
        uint256 secondPoolUsage
    );
    event ShareReleased(
        uint256 indexed memberIndex,
        address indexed member,
        uint256 poolCredit,
        uint256 attackerPayment
    );
    event Withdrawn(address indexed member, uint256 amount);

    error AlreadyConfigured();
    error AlreadyCompleted();
    error DuplicateMember();
    error IncorrectFunding();
    error InvalidMember();
    error InvalidMemberSet();
    error InvalidPoolState();
    error NotConfigured();
    error NotPoolController();
    error NothingToWithdraw();
    error TransferFailed();

    constructor(address controller, address[7] memory committee) {
        if (controller == address(0)) revert InvalidMember();
        poolController = controller;

        for (uint256 i = 0; i < COMMITTEE_SIZE; i++) {
            if (committee[i] == address(0)) revert InvalidMember();
            for (uint256 j = 0; j < i; j++) {
                if (committee[i] == committee[j]) revert DuplicateMember();
            }
            members[i] = committee[i];
        }
    }

    function configureCredits(uint256[7] calldata candidate) external payable {
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

    function acquireFour(uint8[4] calldata memberIndices) external payable {
        if (!configured) revert NotConfigured();
        if (completed) revert AlreadyCompleted();

        uint256 requiredPayment = quoteFour(memberIndices);
        if (msg.value != requiredPayment) revert IncorrectFunding();

        completed = true;
        totalAttackerPayment = requiredPayment;

        for (uint256 i = 0; i < THRESHOLD; i++) {
            uint256 memberIndex = memberIndices[i];
            uint256 directPayment =
                MEMBER_GROSS_FLOOR - credits[memberIndex];
            address member = members[memberIndex];
            claimable[member] += directPayment;
            emit ShareReleased(
                memberIndex,
                member,
                credits[memberIndex],
                directPayment
            );
        }
    }

    function withdraw() external {
        uint256 amount = claimable[msg.sender];
        if (amount == 0) revert NothingToWithdraw();
        claimable[msg.sender] = 0;

        (bool success,) = payable(msg.sender).call{value: amount}("");
        if (!success) revert TransferFailed();
        emit Withdrawn(msg.sender, amount);
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
            for (uint256 j = 0; j < i; j++) {
                if (memberIndices[i] == memberIndices[j]) {
                    revert DuplicateMember();
                }
            }
        }
    }
}
