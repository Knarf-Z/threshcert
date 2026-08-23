# OPE boundary-complete authenticated relative-process certificate

This fixture composes the admitted OverlappingPoolEscrow runtime with seven
real Python operator HTTP processes implementing a 4-of-7 threshold decryption.
For the fixed credit vector [2,0,0,0,2,0,0], it executes every one of the 35
terminal choices and checks an exact attacker net cost of four accounting units
inside an authenticated boundary whose acquisition-linked flows and reuse
surface are explicitly manifested.

Run from the repository root:

~~~text
python reproduce_v16_experiments.py
~~~

The positive certificate checks:

| Gate | Executable evidence |
|---|---|
| P1 | EIP-191 request authentication and commitment-valid plaintext delivery |
| P2* | five manifests cover control accounts, acquisition-linked funding/return paths, the settlement surface, the reuse namespace, and horizon closure; every manifest is bound to the scope ID, header, session set, and all 35 routes |
| P3 | six mined confirmations before operator dispatch and delivery |
| P4 | closed contract mutating ABI, zero buyer claimable balance, no buyer refund/rebate/withdraw route, no service economic-transfer API, and persistent nonce/receipt single use |
| P5 | the fixed C6 root has 35 forward and 35 reverse records, and all 35 complete contract-plus-threshold routes replay |

The checker rejects receipt/nonce reuse, session swapping, a tampered
Chaum--Pedersen proof, three-response delivery, pre-finality delivery, missing
forward/reverse routes, and cost tampering. The independent P2* checker also
reconstructs the five manifests from the EVM capture, refinement certificate,
and contract source. Eight semantic mutations are rebound after tampering so they
cannot fail merely because of a stale digest. The six boundary mutations return
a specific `BOUNDARY-UNKNOWN` reason:

- deleted control account;
- hidden attacker-funding path;
- hidden return interface;
- undeclared cross-session reuse;
- two-session route splice;
- changed settlement horizon;
- deleted successful route (`EXACTNESS-NOT-ESTABLISHED`); and
- changed attainment cost (`LOWER-BOUND-CERTIFIED(4)`).

The machine-readable v3 certificate is
`results/ope_process_positive.v3.json`; its JSON Schema is
`schema/ope_process_certificate.schema.json`. A standard-library verifier that
does not import the generator or runtime recomputes the input bindings,
accounting, route coverage, 140 response signatures, 140 Chaum--Pedersen
proofs, threshold reconstruction, and commitment-valid deliveries:

~~~text
python artifact/ope_process_positive/verify_process_certificate.py
~~~

To regenerate and then byte-check the committed P2* mutation results, run:

~~~text
python artifact/ope_process_positive/verify_process_certificate.py --write-mutations
python artifact/ope_process_positive/verify_process_certificate.py --verify-mutations
~~~

The size and scaling experiment runs the verifier at 1, 5, 10, 20, and 35
cryptographically checked routes. Prefixes are timing probes only; only the
35-route run is a complete certificate:

~~~text
python artifact/ope_process_positive/benchmark_certificate_verifier.py --verify
~~~

The verdict is deliberately authenticated and relative:

~~~text
RELATIVE-PROCESS-CERTIFIED(4)
~~~

It applies only to the authenticated local composition and the declared
acquisition horizon. P2* establishes boundary completeness against the pinned
capture, refinement certificate, source, runtime and session set; it does not
discover activity outside those authenticated anchors. The EVM is Hardhat, the
six confirmations are locally mined, the dealer keys are deterministic artifact
keys, and gas, OS compromise, side channels, activity outside the declared
boundary, and economic independence of the seven operators remain outside the claim.

The value four is not inconsistent with the historical two-host V6 value ten.
They use different admitted route languages, ledgers, and accounting units.
`../COST_DOMAIN_REGISTRY.json` records both claim domains explicitly.
