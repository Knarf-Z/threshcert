# Reproduced results summary

## Certificate checks

- Public-only four-of-seven certificate: `0`, with every positive target
  rejected.
- Controlled nonuniform resistance ledger: `11,500` against target `10,000`.
- Controlled uniform penalty ledger with complete evidence: `10,000`.
- The same penalty ledger with one unattributable member: `7,500`.
- Activation-ladder AC values: `5, 14, 23, 32, 41`, while TC remains `5`.
- Exact bottleneck-allocation values for budgets `0,2,4,6,8,10`:
  `6,7,8,9,10,11`.

## Defense lattice and Möbius checks

- All `18/18` pure high-order instances passed exact rational-arithmetic
  checks.
- Every nonempty proper Möbius coefficient was exactly zero in those instances.
- Dropping the full-order coefficient underpredicted the complete-defense value
  by factors up to `100` in the tested family.
- All 100 seeded random four-of-seven instances were monotone.
- Median maximum relative truncation errors were approximately `0.348`, `0.253`,
  and `0.214` after retaining interactions through orders one, two, and three.
- The target upper sets had between 1 and 10 inclusion-minimal remediation
  plans, with median 6.
- On the random four-of-seven allocation instances, the minimum greedy gain
  ratios were `1.000`, `0.896`, and `0.759` for budgets one, two, and three.
- In the constructed decoy family, the greedy-to-optimal gain ratio fell to
  approximately `0.00005005`.

## Historical calibration checks

- Transfer-join family: `1,672,005` settlement transactions and approximately
  `97.936%` transaction-level USD coverage over its recorded window.
- Separate dex.trades family: `1,286,721` settlement transactions,
  `1,285,403` with USD values, and approximately `99.898%` coverage.
- The dex.trades notional proxy is approximately USD `872.7M`; transaction-level
  proxy percentiles are approximately USD `23.30`, `758.76`, `1,775.91`, and
  `10,410.11` at p50, p90, p95, and p99.
- All 10 deterministic Dune consistency checks passed.

## Repeated exact-solver scaling

- Ten raw repeats were retained on a 13th Gen Intel Core i7-13650HX with 14
  physical cores, 20 logical processors, 16,849,256,448 bytes of RAM, and
  Python 3.11.1.
- At `n=18` (`262,144` subset states), median wall time was `7.495092400` s;
  the inclusive IQR was `[7.335106825, 15.913192750]` s.
- The observed `n=18` range was `7.166669800` to `24.417574700` s and peak
  traced memory was `4.253922462` MiB.
- No timing run was deleted. The median/IQR are primary because three `n=18`
  runs show substantial system-noise inflation.

## Deployment implementation status

- Six Solidity/Hardhat tests pass, including duplicate-signer rejection,
  verifier binding, deadline enforcement, penalty transfer, and certificate
  recomputation from `8` to `6` bond units in the local harness.
- Three Go cryptographic tests pass: seven-share validation, 4-of-7
  reconstruction, and native Keyper signature binding to instance/eon/identity.
- The official Rolling Shutter v1.4.4 configuration generator was used to
  validate fresh generation of seven distinct Keyper identities.
- The seven-process local Rolling Shutter network completed DKG with threshold
  4. Its evidence exporter validated all seven shares and all seven native
  signatures, validated the stored aggregate key, and reproduced it from four
  shares.
- The public Chiado contract is
  `0x3C16dd5689D67d51c076fe80CB7189041c107721`. All nine deployment and committee
  transactions succeeded, and the frozen committee had seven members,
  threshold four, total bond `7,000,000,000,000` wei, and initial certificate
  `4,000,000,000,000` wei.
- Release job
  `0xe33257d2784a1695ae1e14d9cc5b4852ff78debe7fdbd60b6facd939895b636f`
  was opened successfully. Member 0's validated share was observed 5,350
  seconds before the public release time.
- Slashing transaction
  `0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`
  succeeded at block `22,111,234`, reducing the certificate from
  `4,000,000,000,000` to `3,000,000,000,000` wei.

The historical values are calibration statistics, not resistance estimates,
attack-profit observations, or worst-case value caps. All positive certificate
ledgers in this bundle are controlled inputs rather than production resistance
evidence. The completed pilot is verifier-gated, testnet-only, and single-host;
it must not be described as native on-chain BLS verification, a production
deployment, or seven independent operators.
