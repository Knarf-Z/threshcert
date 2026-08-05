# Claims supported by this experiment (v2)

Frozen artifact: `paid-threshold-response-host1/v2`.
Canonical result: `results/canonical_result.v2.json`.
Run metadata (platform, PIDs, timings): `results/run_metadata.v2.json`.

## Supported

- Real 4-of-7 Shamir threshold ElGamal partial decryptions are generated and
  combined over the RFC 3526 group-14 quadratic-residue subgroup.
- Every partial carries a Chaum–Pedersen proof whose Fiat–Shamir challenge binds
  the operator, its public share, the ciphertext, and the buyer/resource/order
  context; each proof is checked against the operator's public share.
- `Q_c(h)`, the counted responder set, is named by an `aggregation_witness`
  carrying operator identifiers, partial-response hashes, order, buyer, resource,
  epoch and an exact responder bitmap. The evaluator reads it; it does not
  choose the coalition.
- (C2) is instantiated by an `allocation_witness` over the *same* responder
  bitmap, with globally unique debit identifiers, no refund or funding identifier
  allocated twice, `D_i - R_i - F_i >= p_i` per counted responder, and
  `sum_i (D_i - R_i - F_i) <= O(h)`.
- Four quantities are computed by four separate code paths and agree:
  `theory_cover = 10` (closed form on the declared floors), `catalog_certificate
  = 10` (minimum of ledger-derived execution floors over the route catalog),
  `observed_minimum = 10` (minimum realized named-buyer net outflow), and the
  baseline `execution_floor = 10`.
- All `7!/3! = 840` ordered threshold routes are enumerated. Each carries a
  ledger-derived execution floor equal to the sum of its coalition's member
  floors; 24 routes attain the minimum, exactly the orderings of `{1,2,3,4}`.
- The coalition `{4,5,6,7}` reports `execution_floor = 22`, not the cover value.
  No route substitutes the closed form for its own ledger.
- Each of the five ablations refutes exactly its target gate. Across the twenty
  off-diagonal cells there is no further `FAIL_COUNTEREXAMPLE`; the only
  non-`PASS` off-diagonal cell is `B3 = NOT_APPLICABLE` under the wrong-buyer
  ablation, where no named-buyer usable delivery exists for atomicity to apply
  to.
- Missing evidence and refutation are distinguished: absent route-coverage
  evidence gives `B5 = FAIL_CLOSED_MISSING_EVIDENCE` and an overall `UNKNOWN`;
  an explicit bypass trace gives `B5 = FAIL_COUNTEREXAMPLE` and `REFUTED`;
  unrecorded credit/release ordering gives `B3 = FAIL_CLOSED_MISSING_EVIDENCE`
  and `UNKNOWN`.
- The adoption threshold is reproduced: the cover value is positive exactly when
  more than `n - q = 3` members carry positive response floors.
- The weighted-committee dynamic program agrees with brute force on the shipped
  instance and on 200 random instances.
- The canonical result is byte-identical across runs on the same host; PIDs,
  timings and platform strings live only in the run metadata.
- Seven operator processes are spawned on one Windows host; the four counted
  responders of the successful 4-of-7 execution each answer from a distinct
  worker process.

## Not supported

- Deployment-wide route closure. (B5) here is closure within the declared finite
  program language, carried by a `route_coverage_evidence` object whose
  `deployment_wide` field is `false`.
- Hardware-enforced non-exportability. The (C1) witness records the operator
  interface (`respond`, `stop`), the absence of any export operation, and the
  module source hashes; its conclusion is explicitly "C1 proved within the
  declared finite service language". There is no HSM, TEE or attestation.
- Seven independent economic operators, or seven physical failure domains. One
  physical host.
- A production DKG. A trusted deterministic dealer generates the shares so the
  run is reproducible.
- Cryptographic randomness. `random.Random` is a seeded deterministic test
  generator, not a cryptographic RNG; it is used only to make the controlled
  experiment reproducible and says nothing about production key generation.
- Any claim that real-world bribery cost equals the experimental token units.
