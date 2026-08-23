# OPE authenticated relative-process certificate

This fixture composes the admitted OverlappingPoolEscrow runtime with seven
real Python operator HTTP processes implementing a 4-of-7 threshold decryption.
For the fixed credit vector [2,0,0,0,2,0,0], it executes every one of the 35
terminal choices and checks an exact authenticated relative-process attacker
net-cost floor of four accounting units.

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

The machine-readable v2 certificate is
`results/ope_process_positive.v2.json`; its JSON Schema is
`schema/ope_process_certificate.schema.json`. A standard-library verifier that
does not import the generator or runtime recomputes the input bindings,
accounting, route coverage, 140 response signatures, 140 Chaum--Pedersen
proofs, threshold reconstruction, and commitment-valid deliveries:

~~~text
python artifact/ope_process_positive/verify_process_certificate.py
~~~

The size and scaling experiment runs the verifier at 1, 5, 10, 20, and 35
cryptographically checked routes. Prefixes are timing probes only; only the
35-route run is a complete certificate:

~~~text
python artifact/ope_process_positive/benchmark_certificate_verifier.py --verify
~~~

The verdict is deliberately authenticated and relative:

~~~text
AUTHENTICATED-RELATIVE-PROCESS-CERTIFIED(4)
~~~

It applies to the admitted local composition only. The EVM is Hardhat, the six
confirmations are locally mined, the dealer keys are deterministic artifact
keys, and gas, OS compromise, side channels, undeclared external transfers, and
economic independence of the seven operators remain outside the claim.

The value four is not inconsistent with the historical two-host V6 value ten.
They use different admitted route languages, ledgers, and accounting units.
`../COST_DOMAIN_REGISTRY.json` records both claim domains explicitly.
