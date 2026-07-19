# Experiment inventory and interpretation boundaries

## Production deployment evidence audit

1. Archival Gnosis snapshot: fixes `2026-06-13T00:00:00Z` to block
   `46,666,718` and its hash, then records the manager, active Keyper-set index
   and contract, activation block, creation and registration transactions,
   finalization state, member order, and four-of-seven threshold.
2. Seven-member evidence ledger: binds each real member address to separate
   resistance, activation, attribution, forfeiture, joint enforcement
   probability, and insurance or compensation fields. Unknown actual
   resistance is never encoded as an observed zero.
3. Evidence-gated production certificate: counts only directly audited
   resistance or a complete attributable and enforceable penalty path. It
   writes a member-level CSV and machine-readable JSON containing both missing
   direct and missing penalty paths.
4. Evidence-gap analysis: computes the current number of positive member
   floors, the minimum number required for a positive threshold certificate,
   and the exact target condition. For the pinned four-of-seven set, at least
   four member floors must be strictly positive and the sum of the four
   smallest floors must reach target `B`.
5. Optional live snapshot verification: uses a standard-library archival RPC
   client to recheck the fixed block, contracts, `KeyperSetAdded` event,
   creation receipt, seven members, and threshold. This is not required by the
   deterministic offline reproduction command.

The present result has seven verified membership rows, zero positive certified
member floors, and four additional positive floors needed. This is a real
deployment evidence audit whose current certificate is zero; it is not a claim
that actual member resistance is zero.

## Controlled certificate and mechanism checks

6. Public-evidence compatibility view: checks that the address-level production
   ledger maps to the same zero threshold-cover lower bound.
7. Controlled positive resistance ledger: checks the threshold-cover verifier.
8. Penalty-evidence gate: compares complete attribution and enforcement
   evidence with one unattributable member.
9. Activation ladder: checks the controlled TC/AC gap.
10. Mechanism-scope stress test: compares sequential, simultaneous, package,
    and robust-threshold-cover values in the stated controlled family.
11. Defensive allocation: computes cheapest-resistance, weight-cycle, and
    exact bottleneck allocations, including every increment and cover cost.
12. Enforceability sensitivity: varies one certified probability lower bound.
13. Exact subset-state scaling: records machine-specific runtime and memory.
    Ten supplied repeats are summarized with median and inclusive IQR; no run
    is removed as an outlier.

These checks exercise certificate branches and check the reference
implementation. They do not empirically validate production resistance.

## Defense lattice and Möbius checks

14. Pure high-order interaction: exact sequential instances for several `k`
    and `M`, with every nonempty proper Möbius coefficient equal to zero.
15. Low-order truncation: measures the arbitrary underprediction caused by
    dropping the full-order coefficient.
16. Seeded random four-of-seven interactions: 100 instances with interaction
    mass by order and truncation errors.
17. Target upper sets: enumerates inclusion-minimal target-achieving plans.
18. Exact versus marginal-greedy allocation on the random instances.
19. Greedy-decoy failure: checks a fixed certified-family construction in
    which local positive marginal gains divert greedy allocation from the
    coordinated optimum.

## Historical calibration checks

20. Dune export validation: reconciles daily counts, transfer coverage,
    selected coverage-curve rows, and dex.trades aggregate statistics.
21. Historical target calibration: reports selected empirical coverage values
    while marking every value as calibration-only.

## Scalability, sensitivity, and baseline checks

22. Committee-size scalability: reports exact subset-state counts and the
    median, inclusive IQR, range, and peak traced memory from all ten retained
    laptop repeats for `n=8,10,12,14,16,18`.
23. Certificate-computation cost: contrasts the `O(n log n)` sorting proxy for
    a uniform threshold-cover certificate with the `2^n` state count of the
    generic exact subset-state method for committee sizes through `n=448`.
24. Parameter sensitivity: evaluates 48 controlled combinations covering
    thresholds `3/7` through `6/7`, four equal-mean resistance distributions,
    and zero, one, or two initially exposed shares.
25. Baseline comparison: compares public-only zero, a certified
    minimum-member-floor bound, the exact lower-tail threshold certificate,
    and an explicitly uncertified mean-resistance heuristic.

## Controlled public-testnet enforcement pilot

26. Seven Solidity/Hardhat checks for a seven-member four-of-seven bonded
    committee, verifier-only evidence, deadline enforcement, binding of every
    signed evidence field, duplicate-signer rejection, nonuniform-bond
    certificate computation, penalty transfer, and certificate update.
27. Seven-process Rolling Shutter v1.4.4 overlay with fresh runtime keys, DKG,
    individual decryption-share persistence, and a fixed four-of-seven
    threshold.
28. Go evidence export requiring seven uniquely indexed valid BLS shares,
    seven uniquely indexed valid native Keyper signatures, a valid stored
    aggregate key, and equality with a four-share reconstruction.
29. Chiado deployment, release-job, and verifier-gated slashing scripts that
    record transaction hashes, blocks, gas, timing, and certificate changes
    without recording private keys.
30. Read-only live-chain verification of all 11 receipts, exact deployment
    bytecode and constructor arguments, slashing calldata and event fields, and
    current contract state through a Chiado RPC endpoint.
31. A deterministic machine-readable Chiado execution certificate binding the
    contract, exporter, Keyper set, four run records, and live verifier by
    SHA-256; it recomputes the four-smallest-bonds value from `4e12` to `3e12`
    wei and records the production-transfer exclusions in the certificate.

## Completed observations and scope boundary

- The archival production snapshot and every member address were checked
  against Gnosis RPC state; the offline artifact retains all fixed identifiers
  needed to repeat that verification.
- The Docker DKG, seven-share evidence export, public Chiado deployment,
  release job, and verifier-gated slashing transaction completed successfully.
  Their records and hashes are cross-checked by bundle-integrity tests.
- The Chiado seven Keypers are seven processes on one host, not independently
  governed production operators. Its positive `3e12`-wei result is an observed
  testnet bond-floor certificate inside that instrumented mechanism.
- The production audit and Chiado pilot are separate evidence domains. The
  pilot cannot fill missing production member rows, and the controlled
  arithmetic checks cannot supply real member inputs.
