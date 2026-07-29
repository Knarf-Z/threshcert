# Finite overlapping-pool RPC fixture

This package instantiates the paper's finite auditable four-of-seven
overlapping-pool construction.

- Each of seven members has gross floor 2.
- Pool 1 covers members 0--3 and has cap 2.
- Pool 2 covers members 3--6 and has cap 2.
- Contract credits are restricted to 0, 1, or 2 units.
- A successful acquisition selects exactly four distinct members and pays
  residual price `2 - credit` to each.

One model unit is encoded as `1 ether` only to obtain exact integer arithmetic
in the local EVM. It is not an ETH-denominated economic calibration.

The contract therefore has exactly 117 admissible credit states and 35
four-member sets. The tests classify all \(3^7=2{,}187\) integer candidates,
invoke its state validator and quote function on all 4,095 admissible
state--set pairs, compare every quote with an independent arithmetic formula,
check that the minimum residual payment is 4, verify that every individual
residual floor is zero, and execute an exact minimizing state-changing
transaction. Negative tests also reject fractional credit and duplicate
member sets.

## Reproduce

With Node.js 24 LTS:

```text
npm ci --no-audit --no-fund
npm run ready
npm run manifest:check
```

Expected test summary:

```text
4 passing (4 nodejs)
```

No RPC endpoint, wallet, secret, or public transaction is used.

## Claim boundary

This fixture verifies the finite public-state relation, the residual-price
rule, exact payment conservation, and the 4-unit minimum at contract level.
The pool controller is a controlled test account. The fixture does not prove
that pool funds are ultimately independent of an attacker, establish
production member costs, or measure a real collusion price.
