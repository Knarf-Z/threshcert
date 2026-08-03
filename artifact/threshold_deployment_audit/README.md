# Data-driven public-evidence evaluation

This directory asks whether typed public records certify a named acquirer's net
irreversible outflow for threshold acquisition. The four-deployment cohort and
the original checklist were author-frozen before the reported audit, but the
freeze was not independently preregistered and does not support a prevalence
claim. Earlier manuscript work had already found the Shutter zero;
post-selection bias cannot be excluded. No project is said to have made the
paper's payment claim, and zero is not an insecurity finding.

## v48 compiler inputs

- `cohort.v1.json` and `data/capture.public.v1.json` preserve the frozen public
  cohort and structured capture.
- `policy.public-evidence.v2.json` defines the complete claim header, five gates,
  and the statuses `PASS`, `FAIL_CLOSED_MISSING_EVIDENCE`,
  `FAIL_COUNTEREXAMPLE`, `UNKNOWN`, and `NOT_APPLICABLE`.
- `data/records_v48/*.json` contains one structured record per public case plus
  two separately labelled finite-state diagnostics. Every gate names exact
  source references; no gate conclusion is shared across systems.
- `data/raw_v48/` preserves 10 official pages, 23 API responses, three fixed
  RPC responses, and their indexes. Dynamic recapture bytes are not assumed to
  equal the earlier frozen digest.
- `results/bridge_audit.v2.json` and
  `results/raw_capture_integrity.v48.json` are canonical compiler outputs.

`scripts/evaluate_offline_v48.mjs` contains no deployment identifier or
prewritten system verdict. It validates the scope schema and source hashes,
checks the finite-LTS evidence type, derives every gate status, writes
`results/bridge_audit.generated.json`, and computes a positive certificate from
the finite LTS's shortest successful path. Input records contain neither gate
verdicts nor certificate floors; missing obligations are derived from policy and the
evidence list. The reference evaluator accepts only nonnegative safe-integer
base-unit amounts; the abstract logic may instead use exact rationals. Every
admitted success state must be terminal for the accounting window, and every
positive prefund must originate in the named-acquirer control class; otherwise
evaluation fails closed.
`verify_offline_v48.mjs` reruns it, byte-compares generated and canonical bytes,
checks that no public record name occurs in evaluator source, verifies the
positive and one-gate-failure diagnostics, and exhausts 1,024 positive-evidence
refinements for monotonicity.

## Offline verification

From the artifact root:

```text
node threshold_deployment_audit/verify_offline_v48.mjs
node threshold_deployment_audit/scripts/verify_raw_capture_v48.mjs
```

The legacy filenames are compatibility wrappers for the v48 scripts. Live
recapture is optional, read-only, and requires a user-supplied archive RPC for
historical code queries; it is not needed for integrity verification.