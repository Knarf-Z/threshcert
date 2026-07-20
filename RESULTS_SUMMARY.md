# Reproduced results summary

## Production deployment evidence audit

- The audit anchor is Gnosis block `46,666,718` at
  `2026-06-13T00:00:00Z`, hash
  `0x574ec26ee7b2e2bfddd991bf99d37a79455428bc4dfe342b0ccf55d071229b60`.
- Manager `0x7C2337f9bFce19d8970661DA50dE8DD7d3D34abb` selects Keyper-set index 10,
  contract `0xE817E77109e2E6a8025eB30dB3542eC18bBDE828`, with seven members and
  threshold four. The optional archival-RPC verifier confirmed the block,
  creation receipt, `KeyperSetAdded` event, set state, member order, and
  threshold.
- All `7/7` real member addresses have verified committee membership. Each row
  audits direct resistance, activation, attribution, forfeiture, joint
  execution probability, and insurance or compensation. No retained row has a
  positive auditable floor on either the direct or penalty-backed path.
- The seven certified member floors are `0,0,0,0,0,0,0`; actual member
  resistance remains `UNKNOWN_NOT_MEASURED`. The zero is an evidence-supported
  lower bound, not an estimate of actual resistance.
- A positive four-of-seven certificate needs at least four strictly positive
  member floors, so the current evidence gap is four members. A target `B`
  requires the sum of the four smallest certified member floors to be at least
  `B`.
- No member-specific activation evidence is certified, so the audit retains
  threshold cover rather than claiming the activation-respecting branch. The
  Chiado value is not transferred because its operators, environment, and
  mechanism differ.

## Certificate checks

- Public-only four-of-seven certificate: `0`, with every positive target
  rejected.
- Deterministic counterfactual check on the pinned committee geometry: public
  `0`; resistance-only TC `4` with cover `{2,3,4,5}`; activation AC `10` with
  witness `(0,1,2,3)`; and robust fallback `4` when the ordered-witness or
  exposure-sufficiency gate is disabled. All 21 choices of two seed-member
  positions return `(TC=4, AC=10)`. The positive values belong to the separate
  counterfactual ledger `I_cf` and use normalized cost units.
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

## Generalized committee-shape sweep

- All 100 seeded trials were monotone at every one of the four additional
  shapes (3-of-5, 5-of-9, 6-of-11, 7-of-13): `0` monotonicity failures each.
- Median maximum relative truncation errors after retaining interactions
  through order one/two/three: `0.310/0.188/0.112` (3-of-5), `0.341/0.271/0.262`
  (5-of-9), `0.342/0.251/0.289` (6-of-11), and `0.374/0.276/0.367` (7-of-13).
  Error does not decrease monotonically with retained order at every shape
  (order three exceeds order two at 6-of-11 and 7-of-13); this is an expected
  property of a signed Möbius expansion, not a computation error, and was
  cross-checked exactly against the original `O(3^n)` per-mask reference
  routine on a held-out instance (`0` mismatches across `1,536` compared
  values).
- Minimum greedy gain ratios by budget: budget one is exactly `1.000` at every
  shape; budget two ranges from `0.473` (3-of-5) to `0.949` (6-of-11); budget
  three ranges from `0.418` (3-of-5) to `0.898` (6-of-11). The qualitative
  finding from the n=7 experiment -- greedy is exact at budget one and can
  degrade at higher budgets -- generalizes across all four shapes.

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

## Extended scalability, sensitivity, and baselines

- Exact subset states rise from `256` at `n=8` to `262,144` at `n=18`.
  Across the ten retained repeats, median runtime rises from `0.000683300` to
  `7.495092400` seconds, a measured factor of approximately `10,968.96` on the
  recorded laptop.
- For the uniform threshold-cover special case, sorting gives an `O(n log n)`
  computation path. At `n=448`, the recorded comparison is a sorting-work
  upper proxy of `4,032` against `2^448` generic subset states. This is a model
  comparison, not a measured `n=448` runtime.
- The parameter grid contains 48 controlled cases. At threshold `4/7` and zero
  initial exposure, exact certificates are `40`, `34`, `16`, and `18` for the
  uniform, balanced, bimodal, and heavy-lower-tail profiles respectively, even
  though all four profiles have mean resistance `10`.
- Certificates increase with threshold and decrease with initial exposure in
  every tested profile. For the heavy-lower-tail profile at zero exposure, the
  values at thresholds `3/7`, `4/7`, `5/7`, and `6/7` are `10`, `18`, `29`,
  and `45`.
- The public-only baseline remains the certified zero bound. On the heavy-tail
  `4/7` case, the certified minimum-member-floor baseline is `4` versus the
  exact lower-tail value `18`; the mean-resistance heuristic reports `40` but
  is explicitly marked uncertified because it can overstate the certificate.

## Boundary and larger-committee sensitivity

- All-zero resistance profile: the certificate is exactly `0` at every tested
  threshold and exposure combination, as required.
- Single-dominant-member profile `(100,1,1,1,1,1,1)`: the certificate stays at
  the number of shares required (`1` through `6`) while unanimity is not
  required, then jumps to `106` at full unanimity (`q=7`) once the dominant
  member's resistance must be included -- an 18x jump from the `q=6` value of
  `6`, illustrating how concentrated resistance mass can make the threshold
  cover certificate highly sensitive to whether the last share is required.
- Degenerate threshold margins (`q=1` and `q=7`) on the original four profiles
  reproduce the same monotone pattern seen in the 48-row table, extended to
  its two endpoints.
- Larger committees built by tiling the original profile shapes: at `n=14`
  (double the original committee, threshold held at the `4/7` ratio, so
  `q=8`), certificates are `80`, `68`, `32`, and `36` for the uniform,
  balanced, bimodal, and heavy-lower-tail profiles; at `n=28` (`q=16`), they
  are `160`, `136`, `64`, and `72`. Each is exactly double (`n=14`) or
  quadruple (`n=28`) its `n=7` counterpart at the matching per-tile share
  count, as expected from tiling identical resistance values.

## Deployment implementation status

- Seven Solidity/Hardhat tests pass, including duplicate-signer rejection,
  nonuniform-bond certificate computation, binding every verifier-signed evidence
  field, deadline enforcement, penalty transfer, and certificate recomputation
  from `8` to `6` bond units in the local harness.
- Four Go tests pass: seven-share validation, 4-of-7 reconstruction, native
  Keyper signature binding to instance/eon/identity, and rejection of duplicate
  or out-of-range Keyper indices.
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
- The read-only `verify:chiado:live` command independently checks all 11 public
  transaction receipts, exact deployment bytecode and constructor arguments,
  slashing calldata/event fields, and the current contract state through a
  Chiado RPC endpoint; it requires no wallet private key. As last run
  (2026-07-20) it still returned `PASS`, with total bond `6,000,000,000,000`
  wei and certificate `3,000,000,000,000` wei live on Chiado.
- The machine-readable certificate
  `deployment/certificates/chiado-execution-certificate.json` independently
  recomputes the four-smallest-bonds values, binds nine source artifacts by
  SHA-256, and reports
  `POSITIVE_WITHIN_RECORDED_TESTNET_MECHANISM`. Its stored post-slashing value is
  `3,000,000,000,000` wei.

The historical values are calibration statistics, not resistance estimates,
attack-profit observations, or worst-case value caps. All positive certificate
ledgers in this bundle are controlled inputs rather than production resistance
evidence. The completed pilot is verifier-gated, testnet-only, and single-host;
it must not be described as native on-chain BLS verification, a production
deployment, or seven independent operators.

The pinned-geometry counterfactual reuses only the verified seven-member,
four-of-seven structure. Its resistance and activation floors are hypothetical,
and its positive values are conditional, so it must not be described as a
Gnosis activation experiment, production validation, measured Keyper
resistance, or any production cost estimate.

The positive Chiado value and the production evidence-audit result are not the
same claim. The former certifies an executed bond-floor state inside the
instrumented testnet mechanism. The latter binds seven real production member
addresses and reports exactly which resistance, activation, attribution,
forfeiture, insurance or compensation, and enforcement-probability evidence is
missing from each row.

Likewise, the extended sensitivity and baseline numbers, the boundary and
larger-committee rows, and the generalized committee-shape sweep are all
normalized or seeded controlled constructions, not observations of production
Keyper resistance. The scalability times are tied to the recorded machine and
Python implementation.
