# Claim boundary

## What a completed public run establishes

- Three Chiado contracts execute the same member-bound, nonreplayable
  enforcement mechanism.
- Four sequential submissions, one four-member atomic package, and two
  repeated two-member packages produce the same four-bond loss, independent
  of the chosen testnet denomination.
- Public receipts, deployment input, state, events, signatures, caller reward
  withdrawal, and treasury accrual can be recomputed through an independent
  RPC endpoint.
- No external package-size or invocation bound is used.

## What it does not establish

- Silent raw-share transfers or evidence-free private leakage are not covered.
- The configured verifier can be compromised, unavailable, or censored.
- The seven signing keys and three contracts are controlled by one experiment,
  not seven independent organizations.
- The experiment does not measure production collusion prices or certify the
  behavioral inputs needed to turn member loss into attacker payment.
- Compensation, common control, and side payments outside the declared ledger
  remain out of scope.
- The deliberately small Chiado bonds are testnet accounting units, not an
  economic stake calibration for production.

If any covered premise fails, the affected channel receives no positive
certificate from this experiment.
