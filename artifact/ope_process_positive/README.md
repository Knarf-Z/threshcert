# OPE controlled positive process certificate

This fixture composes the admitted OverlappingPoolEscrow runtime with seven
real Python operator HTTP processes implementing a 4-of-7 threshold decryption.
For the fixed credit vector [2,0,0,0,2,0,0], it executes every one of the 35
terminal choices and checks an exact relative attacker net-cost floor of four
accounting units.

Run from the repository root:

~~~text
python reproduce_v16_experiments.py
~~~

The positive certificate checks:

| Gate | Executable evidence |
|---|---|
| P1 | EIP-191 request authentication and commitment-valid plaintext delivery |
| P2 | disjoint attacker/controller/member roles and seven signed member/operator bindings |
| P3 | six mined confirmations before operator dispatch and delivery |
| P4 | closed contract mutating ABI, zero buyer claimable balance, no buyer refund/rebate/withdraw route, no service economic-transfer API, and persistent nonce/receipt single use |
| P5 | the fixed C6 root has 35 forward and 35 reverse records, and all 35 complete contract-plus-threshold routes replay |

The checker rejects receipt/nonce reuse, session swapping, a tampered
Chaum--Pedersen proof, three-response delivery, omitted return-interface
evidence, pre-finality delivery, missing forward/reverse routes, cost tampering,
and an undeclared cross-session return.

The verdict is deliberately relative:

~~~text
PROCESS-LEVEL-CERTIFIED(4)
~~~

It applies to the admitted local composition only. The EVM is Hardhat, the six
confirmations are locally mined, the dealer keys are deterministic artifact
keys, and gas, OS compromise, side channels, undeclared external transfers, and
economic independence of the seven operators remain outside the claim.
