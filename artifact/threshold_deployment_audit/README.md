# Finite-LTS public-evidence checker

This directory checks whether typed records certify a named acquirer's net
irreversible outflow for threshold acquisition. It consumes an explicitly
materialized finite acquisition LTS. It does not synthesize entries, callbacks,
proxy or upgrade behavior from bytecode, and it does not discover leak,
coercion, theft, common-control, reimbursement, or other off-chain routes.
A deployment-wide lift therefore requires an independent route-completeness or
success- and payment-preserving refinement proof.

The four public records are author-selected worked diagnostics. The cohort
freeze was not independently preregistered, prior work had already found the
Shutter zero, and no prevalence claim follows. All five gate-evidence arrays are
empty in each public record. Their zeros are record-derived missing-evidence
outputs, not routes independently inferred by the checker, project claims, or
findings of insecurity.

## v49 inputs and outputs

- cohort.v1.json and data/capture.public.v1.json preserve the selected public
  cases and structured capture.
- policy.public-evidence.v3.json fixes the claim header, five gates, status
  vocabulary, and the explicit-LTS input boundary.
- data/records_v49/*.json contains one record per public case plus two
  separately labelled constructed diagnostics.
- data/raw_v48/ preserves the v48 frozen raw capture: 10 official pages,
  23 API responses, three fixed RPC responses, and their indexes. The v48
  suffix dates the capture; it is not the checker version.
- results/bridge_audit.v3.json and
  results/raw_capture_integrity.v48.json are canonical outputs.

scripts/evaluate_offline_v49.mjs validates source hashes, the strict
finite-acquisition-lts/v2 schema, B1--B5, and the exact shortest successful
path in the supplied LTS. Every transition must explicitly provide all semantic amount and origin
fields. Parsed-object schema errors make every gate UNKNOWN; duplicate raw JSON
members or lexically inexact number tokens are rejected before evaluation.
Neither path can produce a positive certificate, and no semantic field has a
default value.

JSON number tokens must be canonical nonnegative safe integers. Fractions and
larger integers use reduced rational objects with canonical unsigned decimal
numerator and positive denominator strings. Exponents, decimals, negative
tokens, duplicate members, and underflow are rejected before native numeric
conversion. All addition and comparison use BigInt fractions. B3 also requires
every positive debit counted on a mapped-success prefix to be explicitly
irreversible. The constructed positive
fixture has five states, four transitions, and successful path values four and
seven; the near-pass has four states and three transitions and fails only B5.
Neither is a deployment measurement or buyer-bound cryptographic delivery.

test_finite_lts_v2.mjs runs 40 malformed-schema cases, including the reported
returnToControl/externalFunding omission, wrong and non-finite values, typos,
duplicate identifiers, endpoint errors, and amount-origin conflicts. Eight raw
JSON cases reject duplicate members, underflowing exponents, decimals, and
invalid numeric tokens. Four well-formed semantic counterexamples include a
reversible prefix debit, while four exact-rational and three boundary cases
cover fractions, MAX_SAFE, and a multi-edge sum above MAX_SAFE.
verify_offline_v49.mjs reruns those tests, byte-compares generated and
canonical results, checks the empty public evidence arrays, verifies the two
constructed diagnostics, and exhausts 1,024 positive-evidence refinements.

## Offline verification

From the artifact root:

    node threshold_deployment_audit/verify_offline_v49.mjs
    node threshold_deployment_audit/scripts/verify_raw_capture_v48.mjs

The unversioned evaluator and verifier filenames delegate to v49. Live recapture
is optional, read-only, and requires a user-supplied archive RPC for historical
code queries; it is not needed for integrity verification.
