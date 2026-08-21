# Finite global named-acquirer positive instance (v77)

This directory contains a deliberately small positive instance in which the
entire admitted world is finite: the account set, beneficial-control graph,
initial balances, funding and return events, action alphabet, and successful
routes are explicit in `model.v1.json`.

After compiling and testing the adjacent Hardhat package, replay the independent
certificate with:

```powershell
cd artifact\joint_incidence_refinement
npm ci --no-audit --no-fund
npm run typecheck
npm test
py -3.11 ..\global_named_acquirer_toy\verify_global_named_acquirer_toy.py --verify --self-test
```

The expected result is:

- `GLOBAL-NAMED-ACQUIRER-CERTIFIED(5000000000000000000)` simulated wei;
- B1, B2, B3, B4, and B5 all `PASS`;
- 8 reachable states, 9 enabled transitions, and exactly 2 first-success routes;
- 6/6 single-gate negative controls; and
- 2/2 interface-ablation cases in which local-equals-global would falsely emit
  a positive floor, while the typed ledger returns `MODEL-REFUTED`.

This is a global certificate only relative to the complete declared toy world.
It is not an Internet-wide control-discovery result, a production deployment,
or evidence of five ether of real economic settlement. The Solidity test and
runtime binding prevent the example from being prose-only; the closed-world JSON
and independent Python enumeration discharge the global premises for this one
finite instance.
