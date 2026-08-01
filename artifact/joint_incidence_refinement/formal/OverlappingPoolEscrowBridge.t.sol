// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {OverlappingPoolEscrow} from "../contracts/OverlappingPoolEscrow.sol";

interface Vm {
    function assume(bool condition) external;
    function deal(address account, uint256 balance) external;
    function prank(address sender) external;
}
contract HostileMember {
    OverlappingPoolEscrow private target;

    bool public attempted;
    bool public acquireSucceeded;
    bool public configureSucceeded;
    bool public withdrawSucceeded;

    function arm(OverlappingPoolEscrow escrow) external {
        target = escrow;
    }

    function pull() external {
        target.withdraw();
    }

    receive() external payable {
        attempted = true;
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        uint256[7] memory candidate;
        (acquireSucceeded,) = address(target).call(
            abi.encodeWithSelector(target.acquireFour.selector, selected)
        );
        (configureSucceeded,) = address(target).call(
            abi.encodeWithSelector(
                target.configureCredits.selector,
                candidate
            )
        );
        (withdrawSucceeded,) = address(target).call(
            abi.encodeWithSelector(target.withdraw.selector)
        );
    }
}

contract OverlappingPoolEscrowBridgeProof {
    Vm private constant vm =
        Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint256 private constant ONE = 1 ether;
    uint256 private constant TWO = 2 ether;
    uint256 private constant FOUR = 4 ether;


    function _member(uint256 i) internal pure returns (address) {
        // i is always in [0,6], so the cast is exact.
        // forge-lint: disable-next-line(unsafe-typecast)
        return address(uint160(0x1001 + i));
    }

    function _attacker() internal pure returns (address) {
        return address(0xBEEF);
    }

    function _deploy() internal returns (OverlappingPoolEscrow escrow) {
        address[7] memory committee;
        for (uint256 i = 0; i < 7; ++i) {
            committee[i] = _member(i);
        }
        escrow = new OverlappingPoolEscrow(address(this), committee);
    }

    function _admissible(uint256[7] memory y)
        internal
        pure
        returns (bool)
    {
        uint256 first;
        uint256 second;
        for (uint256 i = 0; i < 7; ++i) {
            if (y[i] > TWO || y[i] % ONE != 0) return false;
            if (i <= 3) first += y[i];
            if (i >= 3) second += y[i];
        }
        return first <= TWO && second <= TWO;
    }

    function _validSet(uint8[4] memory selected)
        internal
        pure
        returns (bool)
    {
        for (uint256 i = 0; i < 4; ++i) {
            if (selected[i] >= 7) return false;
            if (i > 0 && selected[i] <= selected[i - 1]) return false;
        }
        return true;
    }

    function check_EVMInvalidSetReverts(
        uint8[4] memory selected,
        uint256[7] memory y,
        uint256 suppliedValue
    ) public {
        vm.assume(!_validSet(selected));
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        vm.deal(_attacker(), suppliedValue);
        vm.prank(_attacker());
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.acquireFour.selector, selected)
        );
        assert(!success);
    }

    function check_EVMUnauthorizedConfigure(
        address sender,
        uint256[7] memory y,
        uint256 suppliedValue
    ) public {
        vm.assume(sender != address(this));
        vm.assume(sender != address(0));
        OverlappingPoolEscrow escrow = _deploy();
        vm.deal(sender, suppliedValue);
        vm.prank(sender);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        assert(!success);
    }

    function check_EVMConfigureSuccessClosure(
        uint256[7] memory y,
        uint256 suppliedValue
    ) public {
        for (uint256 i = 0; i < 7; ++i) vm.assume(y[i] <= TWO);
        vm.assume(suppliedValue <= FOUR);

        OverlappingPoolEscrow escrow = _deploy();
        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        bool shouldSucceed =
            _admissible(y) && suppliedValue == _creditTotal(y);
        assert(success == shouldSucceed);
        if (success) {
            assert(escrow.configured());
            assert(!escrow.completed());
            assert(escrow.terminalMask() == 0);
            assert(escrow.totalAcquisitionCallValue() == 0);
            assert(escrow.acquirer() == address(0));
            assert(escrow.deliveredShareMask() == 0);
            assert(address(escrow).balance == suppliedValue);
            for (uint256 i = 0; i < 7; ++i) {
                assert(escrow.credits(i) == y[i]);
                assert(escrow.claimable(_member(i)) == y[i]);
                assert(escrow.shareOwner(i) == _member(i));
            }
        }
    }
    function check_EVMOversizeCreditReverts(
        uint256[7] memory y,
        uint256 suppliedValue
    ) public {
        vm.assume(
            y[0] > TWO || y[1] > TWO || y[2] > TWO || y[3] > TWO ||
            y[4] > TWO || y[5] > TWO || y[6] > TWO
        );
        vm.assume(suppliedValue <= FOUR);
        OverlappingPoolEscrow escrow = _deploy();
        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        assert(!success);
    }

    function check_EVMExcessFundingReverts(
        uint256[7] memory y,
        uint256 suppliedValue
    ) public {
        vm.assume(suppliedValue > FOUR);

        OverlappingPoolEscrow escrow = _deploy();
        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        assert(!success);
    }
    function _creditTotal(uint256[7] memory y)
        internal
        pure
        returns (uint256 total)
    {
        for (uint256 i = 0; i < 7; ++i) total += y[i];
    }

    function _configureExact(
        OverlappingPoolEscrow escrow,
        uint256[7] memory y
    ) internal {
        uint256 poolFunding = _creditTotal(y);
        vm.deal(address(this), poolFunding);
        (bool success,) = address(escrow).call{value: poolFunding}(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        assert(success);
    }

    function _residual(
        uint256[7] memory y,
        uint8[4] memory selected
    ) internal pure returns (uint256 total) {
        for (uint256 i = 0; i < 4; ++i) {
            total += TWO - y[selected[i]];
        }
    }

    function _mask(uint8[4] memory selected)
        internal
        pure
        returns (uint8 mask)
    {
        for (uint256 i = 0; i < 4; ++i) {
            mask |= uint8(1) << selected[i];
        }
    }

    function _completeExact(
        OverlappingPoolEscrow escrow,
        uint256[7] memory y,
        uint8[4] memory selected
    ) internal returns (uint256 attackPayment) {
        attackPayment = _residual(y, selected);
        vm.deal(_attacker(), attackPayment);
        vm.prank(_attacker());
        (bool success,) = address(escrow).call{value: attackPayment}(
            abi.encodeWithSelector(escrow.acquireFour.selector, selected)
        );
        assert(success);
        assert(escrow.acquirer() == _attacker());
    }

    function _proveEdge(
        uint256[7] memory y,
        uint8[4] memory selected,
        uint256 wrongPayment,
        address payer
    ) internal {
        vm.assume(_admissible(y));

        OverlappingPoolEscrow escrow = _deploy();
        vm.assume(payer != address(0));
        vm.assume(payer != address(this));
        vm.assume(payer != address(vm));
        vm.assume(payer != address(escrow));
        for (uint256 i = 0; i < 7; ++i) {
            vm.assume(payer != _member(i));
        }
        uint256 attackPayment = _residual(y, selected);
        assert(attackPayment >= FOUR);
        vm.assume(wrongPayment != attackPayment);

        _configureExact(escrow, y);
        assert(escrow.claimable(payer) == 0);
        (bool reconfigureSuccess,) = address(escrow).call(
            abi.encodeWithSelector(escrow.configureCredits.selector, y)
        );
        assert(!reconfigureSuccess);
        assert(escrow.configured());
        assert(!escrow.completed());
        assert(escrow.terminalMask() == 0);
        assert(escrow.deliveredShareMask() == 0);
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            assert(escrow.shareOwner(i) == _member(i));
        }

        vm.deal(payer, wrongPayment);
        vm.prank(payer);
        (bool wrongPaymentSuccess,) = address(escrow).call{
            value: wrongPayment
        }(abi.encodeWithSelector(escrow.acquireFour.selector, selected));
        assert(!wrongPaymentSuccess);
        vm.deal(payer, attackPayment);
        vm.prank(payer);
        (bool exactPaymentSuccess,) = address(escrow).call{
            value: attackPayment
        }(abi.encodeWithSelector(escrow.acquireFour.selector, selected));
        assert(exactPaymentSuccess);
        assert(escrow.completed());
        assert(escrow.terminalMask() == _mask(selected));
        assert(escrow.deliveredShareMask() == _mask(selected));
        assert(escrow.totalAcquisitionCallValue() == attackPayment);
        assert(escrow.acquirer() == payer);
        assert(escrow.claimable(payer) == 0);
        for (uint256 i = 0; i < 7; ++i) {
            address expectedOwner =
                (uint256(_mask(selected)) & (2 ** i)) != 0
                    ? payer
                    : _member(i);
            assert(escrow.shareOwner(i) == expectedOwner);
        }
        vm.prank(payer);
        (bool replaySuccess,) = address(escrow).call(
            abi.encodeWithSelector(escrow.acquireFour.selector, selected)
        );
        assert(!replaySuccess);
        assert(escrow.completed());
        assert(escrow.terminalMask() == _mask(selected));
        assert(escrow.deliveredShareMask() == _mask(selected));
        assert(escrow.totalAcquisitionCallValue() == attackPayment);
        assert(escrow.acquirer() == payer);
        assert(escrow.claimable(payer) == 0);
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            address expectedOwner =
                (uint256(_mask(selected)) & (2 ** i)) != 0
                    ? payer
                    : _member(i);
            assert(escrow.shareOwner(i) == expectedOwner);
        }
    }

    function check_EVMReconfigureAlwaysReverts(
        uint256[7] memory y,
        uint256[7] memory candidate,
        uint256 suppliedValue
    ) public {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);

        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(
                escrow.configureCredits.selector,
                candidate
            )
        );
        assert(!success);
        assert(escrow.configured());
        assert(!escrow.completed());
        assert(escrow.terminalMask() == 0);
        assert(escrow.deliveredShareMask() == 0);
        assert(escrow.totalAcquisitionCallValue() == 0);
        assert(escrow.acquirer() == address(0));
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            assert(escrow.shareOwner(i) == _member(i));
        }
    }

    function check_EVMCompletedAcquireAlwaysReverts(
        uint256[7] memory y,
        uint8[4] memory replaySelected,
        uint256 replayPayment
    ) public {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        uint256 attackPayment = _completeExact(escrow, y, selected);

        vm.deal(address(this), replayPayment);
        (bool success,) = address(escrow).call{value: replayPayment}(
            abi.encodeWithSelector(
                escrow.acquireFour.selector,
                replaySelected
            )
        );
        assert(!success);
        assert(escrow.configured());
        assert(escrow.completed());
        assert(escrow.terminalMask() == _mask(selected));
        assert(escrow.deliveredShareMask() == _mask(selected));
        assert(escrow.totalAcquisitionCallValue() == attackPayment);
        assert(escrow.acquirer() == _attacker());
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            address expectedOwner =
                (uint256(_mask(selected)) & (2 ** i)) != 0
                    ? _attacker()
                    : _member(i);
            assert(escrow.shareOwner(i) == expectedOwner);
        }
    }
    function _proveRoleConflict(
        address sender,
        uint256[7] memory y
    ) internal {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        uint256 attackPayment = _residual(y, selected);
        vm.deal(sender, attackPayment);
        vm.prank(sender);
        (bool success,) = address(escrow).call{value: attackPayment}(
            abi.encodeWithSelector(escrow.acquireFour.selector, selected)
        );
        assert(!success);
        assert(!escrow.completed());
        assert(escrow.terminalMask() == 0);
        assert(escrow.deliveredShareMask() == 0);
        assert(escrow.totalAcquisitionCallValue() == 0);
        assert(escrow.acquirer() == address(0));
    }

    function check_EVMRoleConflictedController(uint256[7] memory y) public {
        _proveRoleConflict(address(this), y);
    }

    function check_EVMRoleConflictedMember_0(uint256[7] memory y) public {
        _proveRoleConflict(_member(0), y);
    }

    function check_EVMRoleConflictedMember_1(uint256[7] memory y) public {
        _proveRoleConflict(_member(1), y);
    }

    function check_EVMRoleConflictedMember_2(uint256[7] memory y) public {
        _proveRoleConflict(_member(2), y);
    }

    function check_EVMRoleConflictedMember_3(uint256[7] memory y) public {
        _proveRoleConflict(_member(3), y);
    }

    function check_EVMRoleConflictedMember_4(uint256[7] memory y) public {
        _proveRoleConflict(_member(4), y);
    }

    function check_EVMRoleConflictedMember_5(uint256[7] memory y) public {
        _proveRoleConflict(_member(5), y);
    }

    function check_EVMRoleConflictedMember_6(uint256[7] memory y) public {
        _proveRoleConflict(_member(6), y);
    }

    function check_EVMEdge_0123(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0124(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 4];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0125(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0126(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0134(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 3, 4];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0135(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 3, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0136(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 3, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0145(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0146(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0156(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0234(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 3, 4];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0235(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 3, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0236(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 3, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0245(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0246(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0256(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 2, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0345(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 3, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0346(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 3, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0356(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 3, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_0456(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(0), 4, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1234(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 3, 4];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1235(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 3, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1236(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 3, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1245(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1246(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1256(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1345(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 3, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1346(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 3, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1356(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 3, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_1456(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(1), 4, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_2345(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(2), 3, 4, 5];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_2346(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(2), 3, 4, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_2356(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(2), 3, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_2456(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(2), 4, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function check_EVMEdge_3456(
        uint256[7] memory y,
        uint256 wrongPayment,
        address payer
    ) public {
        uint8[4] memory selected = [uint8(3), 4, 5, 6];
        _proveEdge(y, selected, wrongPayment, payer);
    }

    function _proveWithdraw(
        uint256[7] memory y,
        uint8 memberIndex
    ) internal {
        vm.assume(_admissible(y));
        vm.assume(memberIndex < 7);

        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);

        bool configuredBefore = escrow.configured();
        bool completedBefore = escrow.completed();
        uint8 maskBefore = escrow.terminalMask();
        uint8 deliveredBefore = escrow.deliveredShareMask();
        uint256 paymentBefore = escrow.totalAcquisitionCallValue();
        address acquirerBefore = escrow.acquirer();

        vm.prank(_member(memberIndex));
        (bool success,) = address(escrow).call(
            abi.encodeWithSelector(escrow.withdraw.selector)
        );
        assert(success == (y[memberIndex] > 0));

        assert(escrow.configured() == configuredBefore);
        assert(escrow.completed() == completedBefore);
        assert(escrow.terminalMask() == maskBefore);
        assert(escrow.deliveredShareMask() == deliveredBefore);
        assert(escrow.totalAcquisitionCallValue() == paymentBefore);
        assert(escrow.acquirer() == acquirerBefore);
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            assert(escrow.shareOwner(i) == _member(i));
        }
    }

    function check_EVMWithdrawProjectionNeutral_0(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 0);
    }

    function check_EVMWithdrawProjectionNeutral_1(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 1);
    }

    function check_EVMWithdrawProjectionNeutral_2(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 2);
    }

    function check_EVMWithdrawProjectionNeutral_3(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 3);
    }

    function check_EVMWithdrawProjectionNeutral_4(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 4);
    }

    function check_EVMWithdrawProjectionNeutral_5(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 5);
    }

    function check_EVMWithdrawProjectionNeutral_6(uint256[7] memory y)
        public
    {
        _proveWithdraw(y, 6);
    }

    function _assertProjection(
        OverlappingPoolEscrow escrow,
        uint256[7] memory y,
        bool completedBefore,
        uint8 maskBefore,
        uint256 paymentBefore
    ) internal view {
        assert(escrow.configured());
        assert(escrow.completed() == completedBefore);
        assert(escrow.terminalMask() == maskBefore);
        assert(escrow.deliveredShareMask() == maskBefore);
        assert(escrow.totalAcquisitionCallValue() == paymentBefore);
        assert(escrow.acquirer() == (completedBefore ? _attacker() : address(0)));
        for (uint256 i = 0; i < 7; ++i) {
            assert(escrow.credits(i) == y[i]);
            address expectedOwner =
                (uint256(maskBefore) & (2 ** i)) != 0
                    ? _attacker()
                    : _member(i);
            assert(escrow.shareOwner(i) == expectedOwner);
        }
    }

    function _withdrawAs(
        OverlappingPoolEscrow escrow,
        uint8 memberIndex
    ) internal returns (bool success) {
        vm.prank(_member(memberIndex));
        (success,) = address(escrow).call(
            abi.encodeWithSelector(escrow.withdraw.selector)
        );
    }

    function _proveTerminalWithdrawSelected(
        uint256[7] memory y,
        uint8[4] memory selected,
        uint8 memberIndex
    ) internal {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        uint256 attackPayment = _completeExact(escrow, y, selected);
        bool success = _withdrawAs(escrow, memberIndex);
        assert(success);
        _assertProjection(
            escrow,
            y,
            true,
            _mask(selected),
            attackPayment
        );
    }

    function _proveTerminalWithdrawSelectedAfterPoolWithdraw(
        uint256[7] memory y,
        uint8[4] memory selected,
        uint8 memberIndex
    ) internal {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        bool poolWithdrawSuccess = _withdrawAs(escrow, memberIndex);
        assert(poolWithdrawSuccess == (y[memberIndex] > 0));
        uint256 attackPayment = _completeExact(escrow, y, selected);
        bool terminalWithdrawSuccess = _withdrawAs(escrow, memberIndex);
        assert(terminalWithdrawSuccess == (y[memberIndex] < TWO));
        _assertProjection(
            escrow,
            y,
            true,
            _mask(selected),
            attackPayment
        );
    }

    function _proveTerminalWithdrawUnselected(
        uint256[7] memory y,
        uint8[4] memory selected,
        uint8 memberIndex
    ) internal {
        vm.assume(_admissible(y));
        OverlappingPoolEscrow escrow = _deploy();
        _configureExact(escrow, y);
        uint256 attackPayment = _completeExact(escrow, y, selected);
        bool success = _withdrawAs(escrow, memberIndex);
        assert(success == (y[memberIndex] > 0));
        _assertProjection(
            escrow,
            y,
            true,
            _mask(selected),
            attackPayment
        );
    }

    function check_EVMTerminalWithdrawSelected_0(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelected(y, selected, 0);
    }

    function check_EVMTerminalWithdrawSelected_1(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelected(y, selected, 1);
    }

    function check_EVMTerminalWithdrawSelected_2(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelected(y, selected, 2);
    }

    function check_EVMTerminalWithdrawSelected_3(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelected(y, selected, 3);
    }

    function check_EVMTerminalWithdrawSelected_4(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(1), 2, 3, 4];
        _proveTerminalWithdrawSelected(y, selected, 4);
    }

    function check_EVMTerminalWithdrawSelected_5(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 5];
        _proveTerminalWithdrawSelected(y, selected, 5);
    }

    function check_EVMTerminalWithdrawSelected_6(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 6];
        _proveTerminalWithdrawSelected(y, selected, 6);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_0(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 0);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_1(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 1);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_2(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 2);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_3(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 3);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_4(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(1), 2, 3, 4];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 4);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_5(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 5];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 5);
    }

    function check_EVMTerminalWithdrawSelectedAfterPoolWithdraw_6(
        uint256[7] memory y
    ) public {
        uint8[4] memory selected = [uint8(0), 1, 2, 6];
        _proveTerminalWithdrawSelectedAfterPoolWithdraw(y, selected, 6);
    }

    function check_EVMTerminalWithdrawUnselected_0(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(1), 2, 3, 4];
        _proveTerminalWithdrawUnselected(y, selected, 0);
    }

    function check_EVMTerminalWithdrawUnselected_1(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 2, 3, 4];
        _proveTerminalWithdrawUnselected(y, selected, 1);
    }

    function check_EVMTerminalWithdrawUnselected_2(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 3, 4];
        _proveTerminalWithdrawUnselected(y, selected, 2);
    }

    function check_EVMTerminalWithdrawUnselected_3(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 4];
        _proveTerminalWithdrawUnselected(y, selected, 3);
    }

    function check_EVMTerminalWithdrawUnselected_4(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawUnselected(y, selected, 4);
    }

    function check_EVMTerminalWithdrawUnselected_5(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawUnselected(y, selected, 5);
    }

    function check_EVMTerminalWithdrawUnselected_6(uint256[7] memory y)
        public
    {
        uint8[4] memory selected = [uint8(0), 1, 2, 3];
        _proveTerminalWithdrawUnselected(y, selected, 6);
    }
    function _deployHostile()
        internal
        returns (
            OverlappingPoolEscrow escrow,
            HostileMember hostile
        )
    {
        hostile = new HostileMember();
        address[7] memory committee;
        committee[0] = address(hostile);
        for (uint256 i = 1; i < 7; ++i) {
            committee[i] = _member(i);
        }
        escrow = new OverlappingPoolEscrow(address(this), committee);
        hostile.arm(escrow);
    }

    function _assertHostileCallbacksBlocked(HostileMember hostile)
        internal
        view
    {
        assert(hostile.attempted());
        assert(!hostile.acquireSucceeded());
        assert(!hostile.configureSucceeded());
        assert(!hostile.withdrawSucceeded());
    }

    function check_EVMHostileCallbackPreTerminal() public {
        (OverlappingPoolEscrow escrow, HostileMember hostile) =
            _deployHostile();
        uint256[7] memory y;
        y[0] = ONE;
        _configureExact(escrow, y);

        hostile.pull();

        _assertHostileCallbacksBlocked(hostile);
        assert(escrow.configured());
        assert(!escrow.completed());
        assert(escrow.terminalMask() == 0);
        assert(escrow.deliveredShareMask() == 0);
        assert(escrow.totalAcquisitionCallValue() == 0);
        assert(escrow.acquirer() == address(0));
        assert(escrow.credits(0) == ONE);
        assert(escrow.shareOwner(0) == address(hostile));
        assert(escrow.claimable(address(hostile)) == 0);
    }

    function check_EVMHostileCallbackTerminal() public {
        (OverlappingPoolEscrow escrow, HostileMember hostile) =
            _deployHostile();
        uint256[7] memory y;
        y[0] = ONE;
        y[4] = ONE;
        _configureExact(escrow, y);
        uint8[4] memory selected = [uint8(0), 1, 4, 5];
        uint256 attackPayment = _completeExact(escrow, y, selected);

        hostile.pull();

        _assertHostileCallbacksBlocked(hostile);
        assert(escrow.configured());
        assert(escrow.completed());
        assert(escrow.terminalMask() == _mask(selected));
        assert(escrow.deliveredShareMask() == _mask(selected));
        assert(escrow.totalAcquisitionCallValue() == attackPayment);
        assert(escrow.acquirer() == _attacker());
        assert(escrow.shareOwner(0) == _attacker());
        assert(escrow.shareOwner(6) == _member(6));
        assert(escrow.credits(0) == ONE);
        assert(escrow.credits(4) == ONE);
        assert(escrow.claimable(address(hostile)) == 0);
    }
    function _knownSelector(bytes4 selector) internal pure returns (bool) {
        return
            selector == bytes4(keccak256("CREDIT_UNIT()")) ||
            selector == bytes4(keccak256("MEMBER_GROSS_FLOOR()")) ||
            selector == bytes4(keccak256("POOL_CAP()")) ||
            selector == bytes4(keccak256("COMMITTEE_SIZE()")) ||
            selector == bytes4(keccak256("THRESHOLD()")) ||
            selector == bytes4(keccak256("poolController()")) ||
            selector == bytes4(keccak256("members(uint256)")) ||
            selector == bytes4(keccak256("credits(uint256)")) ||
            selector == bytes4(keccak256("configured()")) ||
            selector == bytes4(keccak256("completed()")) ||
            selector == bytes4(keccak256("terminalMask()")) ||
            selector == bytes4(keccak256("deliveredShareMask()")) ||
            selector == bytes4(keccak256("shareOwner(uint256)")) ||
            selector == bytes4(keccak256("totalAcquisitionCallValue()")) ||
            selector == bytes4(keccak256("acquirer()")) ||
            selector == bytes4(keccak256("claimable(address)")) ||
            selector == bytes4(keccak256("configureCredits(uint256[7])")) ||
            selector == bytes4(keccak256("residualPrice(uint256)")) ||
            selector == bytes4(keccak256("quoteFour(uint8[4])")) ||
            selector ==
                bytes4(keccak256("quoteCandidate(uint256[7],uint8[4])")) ||
            selector == bytes4(keccak256("acquireFour(uint8[4])")) ||
            selector == bytes4(keccak256("withdraw()"));
    }

    function check_EVMEntryClosure(
        bytes4 selector,
        uint256 suppliedValue
    ) public {
        OverlappingPoolEscrow escrow = _deploy();
        bytes memory paddedArguments = new bytes(14 * 32);
        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodePacked(selector, paddedArguments)
        );
        if (!_knownSelector(selector)) assert(!success);
    }

    function check_EVMWithdrawValueReverts(uint256 suppliedValue) public {
        vm.assume(suppliedValue > 0);
        OverlappingPoolEscrow escrow = _deploy();
        vm.deal(address(this), suppliedValue);
        (bool success,) = address(escrow).call{value: suppliedValue}(
            abi.encodeWithSelector(escrow.withdraw.selector)
        );
        assert(!success);
    }
}
