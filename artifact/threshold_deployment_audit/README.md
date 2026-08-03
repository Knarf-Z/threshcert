# Prospectively frozen threshold-deployment bridge audit

This directory contains a fixed-cohort audit of whether public records can
certify attacker-funded acquisition payment. The cohort and checklist were
committed before the reported result was generated. This was an
author-controlled, prospectively frozen plan, not independent preregistration:
no external timestamp predates screening, collection followed the same day, and
earlier manuscript work had already established the Shutter zero. Post-selection
bias cannot be excluded. The audit is purposive, not a random sample or a
prevalence estimate, and it does not test a claim made by the four projects.

The frozen inputs are:

- `cohort.v1.json`: four public threshold deployments and their selection rule;
- `policy.bridge-evidence.v1.json`: claim semantics, five bridge gates,
  loss-floor fields, temporal fields, and fail-closed decision rules.

After the freeze, result generation did not change these files. A system passes a positive
attacker-payment claim only when all five bridge gates are supported for the
same deployment, event, time interval, payer, usable-delivery predicate, and
mechanism language. Threshold-only, slashing-only, and self-reported-price
baselines are evaluated separately. Missing evidence produces zero, not a
claim that the system is insecure or that real acquisition would be free.

The audit cutoff is `2026-08-03T02:21:32+08:00`.


## Reproduce

Offline verification from the artifact root:

```text
node threshold_deployment_audit/verify_offline.mjs
```

The live capture script performs read-only network queries and is not part of
the offline one-command verifier:

```text
node threshold_deployment_audit/scripts/capture_live.mjs
node threshold_deployment_audit/scripts/evaluate_offline.mjs
```
