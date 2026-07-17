# Experiment inventory and interpretation boundaries

## Certificate and mechanism checks

1. Public-only four-of-seven certificate: confirms that missing member-level
   evidence produces a zero lower bound.
2. Controlled positive resistance ledger: checks the threshold-cover verifier.
3. Penalty-evidence gate: compares complete attribution/enforcement evidence
   with one unattributable member.
4. Activation ladder: checks the controlled TC/AC gap.
5. Mechanism-scope stress test: compares sequential, simultaneous, package, and
   robust-threshold-cover values in the stated controlled family.
6. Defensive allocation: computes cheapest-resistance, weight-cycle, and exact
   bottleneck allocations, including all member increments and cover costs.
7. Enforceability sensitivity: varies one certified probability lower bound.
8. Exact subset-state scaling: records machine-specific runtime and memory.
   Ten supplied repeats are summarized with median and inclusive IQR; no run is
   removed as an outlier.

## Defense lattice and Möbius checks

9. Pure high-order interaction: exact sequential instances for several `k` and
   `M`, with all nonempty proper Möbius coefficients equal to zero.
10. Low-order truncation: measures the arbitrary underprediction caused by
    dropping the full-order coefficient.
11. Seeded random four-of-seven interactions: 100 instances with interaction
    mass by order and truncation errors.
12. Target upper sets: enumerates inclusion-minimal target-achieving plans.
13. Exact versus marginal-greedy allocation on the random instances.
14. Greedy-decoy failure: checks a fixed certified-family construction in which
    local positive marginal gains divert greedy allocation from the coordinated
    optimum.

## Historical calibration checks

15. Dune export validation: reconciles daily counts, transfer coverage, selected
    coverage-curve rows, and dex.trades aggregate statistics.
16. Historical target calibration: reports selected empirical coverage values
    while marking every value as calibration-only.

## Real-deployment pilot

17. Six Solidity/Hardhat checks for a seven-member 4-of-7 bonded committee,
    verifier-only evidence, deadline enforcement, exact evidence binding,
    duplicate-signer rejection, penalty transfer, and certificate update.
18. Seven-process Rolling Shutter v1.4.4 overlay with fresh runtime keys, DKG,
    individual decryption-share persistence, and a fixed 4-of-7 threshold.
19. Go evidence export that requires seven valid BLS shares, seven valid native
    Keyper signatures, a valid stored aggregate key, and equality with a
    four-share reconstruction.
20. Chiado deployment, release-job, and verifier-gated slashing scripts that
    record transaction hashes, block numbers, gas, timing, and certificate
    changes without recording private keys.

## Completed observation and remaining scope boundary

- The user-run Docker DKG, seven-share evidence export, public Chiado deployment,
  release job, and verifier-gated slashing transaction completed successfully.
  The returned records and public hashes are included and cross-checked by the
  bundle-integrity tests.
- The seven Keypers are seven processes on one host, not independently governed
  production operators.
- The controlled experiment does not establish a production Shutter
  certificate or production-member resistance values.
