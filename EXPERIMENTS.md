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

6. Pinned-geometry counterfactual: keeps the real seven-member, four-of-seven
   committee geometry but uses a separate counterfactual ledger, `I_cf`, to
   supply explicitly hypothetical resistance floors `[4,4,1,1,1,1,1]` and
   activation floors `[0,0,2/7,2/7,2/7,2/7,2/7]`, all in normalized cost
   units. The unified solver returns public `0`,
   resistance-only TC `4`, activation AC `10`, and robust fallback `4` when
   either activation gate is disabled. It records TC cover `{2,3,4,5}`, AC
   witness `(0,1,2,3)`, and all 21 choices of the two seed-member positions.
7. Public-evidence compatibility view: checks that the address-level production
   ledger maps to the same zero threshold-cover lower bound.
8. Controlled positive resistance ledger: checks the threshold-cover verifier.
9. Penalty-evidence gate: compares complete attribution and enforcement
   evidence with one unattributable member.
10. Activation ladder: checks the controlled TC/AC gap.
11. Mechanism-scope stress test: compares sequential, simultaneous, package,
    and robust-threshold-cover values in the stated controlled family.
12. Defensive allocation: computes cheapest-resistance, weight-cycle, and
    exact bottleneck allocations, including every increment and cover cost.
13. Enforceability sensitivity: varies one certified probability lower bound.
14. Exact subset-state scaling: records machine-specific runtime and memory.
    Ten supplied repeats are summarized with median and inclusive IQR; no run
    is removed as an outlier.

These checks exercise certificate branches and check the reference
implementation. The pinned-geometry check is deterministic and counterfactual;
its positive values are conditional and do not empirically validate production
resistance, activation, operator independence, or payment conditions.

## Defense lattice and Möbius checks

15. Pure high-order interaction: exact sequential instances for several `k`
    and `M`, with every nonempty proper Möbius coefficient equal to zero.
16. Low-order truncation: measures the arbitrary underprediction caused by
    dropping the full-order coefficient.
17. Seeded random four-of-seven interactions: 100 instances with interaction
    mass by order and truncation errors.
18. Target upper sets: enumerates inclusion-minimal target-achieving plans.
19. Exact versus marginal-greedy allocation on the random instances.
20. Greedy-decoy failure: checks a fixed certified-family construction in
    which local positive marginal gains divert greedy allocation from the
    coordinated optimum.
21. Generalized committee-shape sweep: repeats checks 17, a truncation-error
    check analogous to 16/18, and check 19 at six additional committee
    shapes (3-of-5, 5-of-9, 6-of-11, 7-of-13, 8-of-15, 9-of-17, 100 seeded
    trials each; the last two were added in a later additive pass), so the
    n=7 findings are not read as an artifact of one committee size. Truncation
    error is computed via a per-order zeta-transform accumulation rather than
    the O(3^n) per-mask subset enumeration used for the single n=7 case, so
    the check stays cheap up to n=17. Additive: does not modify or rerun the
    n=7 experiment, the four originally-added shapes, or any of their
    recorded outputs (each shape's random draws are independently seeded by
    `(n, q)`).

## Historical calibration checks

22. Dune export validation: reconciles daily counts, transfer coverage,
    selected coverage-curve rows, and dex.trades aggregate statistics.
23. Historical target calibration: reports selected empirical coverage values
    while marking every value as calibration-only.

## Scalability, sensitivity, and baseline checks

24. Committee-size scalability: reports exact subset-state counts and the
    median, inclusive IQR, range, and peak traced memory from all ten retained
    laptop repeats for `n=8,10,12,14,16,18`. A later additive pass added one
    further point, `n=20`, in a separate ten-repeat file/summary
    (`results/solver_scaling_repeats_extended*`) reusing the same solver, so
    the original six-point table and its consumer in
    `extended_experiments/` are untouched.
25. Certificate-computation cost: contrasts the `O(n log n)` sorting proxy for
    a uniform threshold-cover certificate with the `2^n` state count of the
    generic exact subset-state method for committee sizes through `n=448`.
26. Parameter sensitivity: evaluates 48 controlled combinations covering
    thresholds `3/7` through `6/7`, four equal-mean resistance distributions,
    and zero, one, or two initially exposed shares.
27. Boundary and larger-committee sensitivity: 64 combinations covering
    degenerate threshold margins (`q=1` and `q=7` on the original n=7
    profiles), an all-zero and a single-dominant-member resistance profile
    swept across the full threshold range, and committee sizes 14 and 28
    built by tiling the original profile shapes and holding the 4-of-7
    threshold ratio (plus full unanimity). Kept in a separate output from
    check 26 so that table's row count and recorded numbers stay unchanged.
28. Baseline comparison: compares public-only zero, a certified
    minimum-member-floor bound, the exact lower-tail threshold certificate,
    and an explicitly uncertified mean-resistance heuristic.

## Independent from-scratch verification

29. A from-scratch reimplementation of the paper's core acquisition-cost
    objects, built only from the formulas in the paper's own text (not the
    authors' code), independently cross-checks all 36 named numbers in
    Section 7, random/exhaustively stress-tests the central equivalence and
    hardening theorems on instances beyond the paper's own hand-picked
    examples, and extends the exact-solver scaling table to n=22 on an
    independent implementation (a later additive pass actually ran and
    recorded one point further, n=24, median 55.99s; see
    `verification_scripts/results/scaling_fast_extended.txt`). A separate
    script checks the replacement-hull
    attribution theorem's two formulas against each other via an exact
    Fraction-equality check on 200 random instances (originally built from
    the theorem statement supplied directly by the paper's author, before
    `main_text.tex` was on this machine, unlike the rest of this suite;
    `main_text.tex` arrived in a later pass and confirms the statement was
    transcribed correctly) plus its separation corollary on three
    hand-picked constructive instances. A further script,
    `information_boundary.py`, stress-tests the central theorem
    (evidence-optimal certificates / information boundary) directly: on 300
    random evidence ledgers it confirms the exact-floor profile attains
    TCR/ACR exactly, and on 1,500 further profiles built strictly above the
    same floors it confirms none ever certifies a smaller attack cost,
    plus a 60-instance public-only check collapsing to exactly zero. A
    fourth script, `partial_activation_evidence.py`, stress-tests the newer
    partial-activation-floor-evidence proposition (the MCR certificate
    between TCR and ACR when only some members' activation floors are
    certified): 200 random instances for boundary/monotonicity checks (0
    mismatches), a further 200 for tightness against the proposition's own
    least-favourable-profile construction (0 mismatches), and 1,000
    perturbed profiles for soundness (0 violations). A fifth script,
    `atomic_bypass_hierarchy.py`, stress-tests the one-shot atomic-bypass
    mechanism hierarchy (ABC_b: at most one atomic, activation-free package
    of at most `b` members across the *entire* attack, not a repeatable
    per-transaction cap, interpolating between the sequential and
    all-or-nothing-package mechanisms): 640 random instances cross-validate
    the theorem's closed form against an independent state-space
    computation that does not assume the package triggers first (0
    mismatches), a further 360 confirm the boundary and monotonicity claims
    (0
    mismatches), and the paper's own four-of-seven counterfactual curve is
    reproduced exactly (10,7,4,4,4,4,4,4). A sixth script,
    `general_package_family_hierarchy.py`, stress-tests the generalization
    of that hierarchy to an arbitrary certified package family with a
    repetition budget (`m_{B,r}`: at most `r` pairwise-disjoint packages
    from a family `B` not necessarily bounded by cardinality): 800 random
    instances with deliberately non-cardinality (exotic) families
    cross-validate the general closed form against an independent
    state-space computation (0 mismatches), a further 1,500 confirm that
    for a cardinality-bounded family the repetition budget is entirely
    redundant (`B_b^{+r} = B_{r*b}` exactly, matching the single-package
    theorem's own closed form, 0 mismatches), and a further 240 confirm
    that once the family contains every singleton, unlimited repetition
    collapses the certificate all the way to TCR (0 mismatches) --
    together showing why the paper's one-shot restriction (`r=1`) is the
    boundary at which the hierarchy stops collapsing, not an arbitrary
    modeling choice. See
    `verification_scripts/README.md` for full per-script coverage and stated
    limitations (this suite cannot catch a shared conceptual mistake that
    both the paper and a from-scratch reimplementation would make the same
    way, and the replacement-hull separation corollary is only checked
    constructively rather than by a general solver).

## Controlled public-testnet enforcement pilot

30. Seven Solidity/Hardhat checks for a seven-member four-of-seven bonded
    committee, verifier-only evidence, deadline enforcement, binding of every
    signed evidence field, duplicate-signer rejection, nonuniform-bond
    certificate computation, penalty transfer, and certificate update.
31. Seven-process Rolling Shutter v1.4.4 overlay with fresh runtime keys, DKG,
    individual decryption-share persistence, and a fixed four-of-seven
    threshold.
32. Go evidence export requiring seven uniquely indexed valid BLS shares,
    seven uniquely indexed valid native Keyper signatures, a valid stored
    aggregate key, and equality with a four-share reconstruction.
33. Chiado deployment, release-job, and verifier-gated slashing scripts that
    record transaction hashes, blocks, gas, timing, and certificate changes
    without recording private keys.
34. Read-only live-chain verification of all 11 receipts, exact deployment
    bytecode and constructor arguments, slashing calldata and event fields, and
    current contract state through a Chiado RPC endpoint.
35. A deterministic machine-readable Chiado execution certificate binding the
    contract, exporter, Keyper set, four run records, and live verifier by
    SHA-256; it recomputes the four-smallest-bonds value from `4e12` to `3e12`
    wei and records the production-transfer exclusions in the certificate.
36. A standalone additive script (`deployment/scripts/report_slashing_fee_ratio.py`)
    recomputes the recorded slashing transaction's own fee from its stored gas
    used and effective gas price and compares it to the bond it forfeited,
    without modifying the certificate file above (whose hash is cited by exact
    value elsewhere): `108,629` gas at `10,000,000,007` wei/gas is
    `1,086,290,000,760,403` wei, versus a `1e12`-wei bond forfeited --
    the attestation cost about `1,086x` the bond it recovered.

## Completed observations and scope boundary

- The archival production snapshot and every member address were checked
  against Gnosis RPC state; the offline artifact retains all fixed identifiers
  needed to repeat that verification. As last run (2026-07-20), the live
  recheck and the live Chiado chain recheck both still returned `PASS`.
- The Docker DKG, seven-share evidence export, public Chiado deployment,
  release job, and verifier-gated slashing transaction completed successfully.
  Their records and hashes are cross-checked by bundle-integrity tests.
- The Chiado seven Keypers are seven processes on one host, not independently
  governed production operators. Its positive `3e12`-wei result is an observed
  testnet bond-floor certificate inside that instrumented mechanism.
- The production audit and Chiado pilot are separate evidence domains. The
  pilot cannot fill missing production member rows, and the controlled
  arithmetic checks cannot supply real member inputs.
- The `0 -> 4 -> 10 -> 4` pinned-geometry result uses hypothetical floors. It
  is not a Gnosis activation experiment, production validation, or measurement
  of Keyper resistance.
- The generalized committee-shape sweep and the boundary/larger-committee
  sensitivity rows are both extensions of the same normalized, seeded, or
  tiled controlled constructions used elsewhere in this inventory; neither
  introduces new production or deployment evidence.
