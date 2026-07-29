# Verification checklist

The independent verifier requires a completed
`results/phase2_chiado.json` and an RPC endpoint chosen independently of the
deployment endpoint.

It rejects the artifact unless all of the following hold:

- chain id is 10200;
- all three deployment inputs match the locally compiled creation bytecode
  and constructor arguments;
- every recorded receipt, block hash, status, and gas value matches Chiado;
- every recorded sender, target, effective gas price, and computed gas cost
  matches Chiado;
- all deployed contracts have the recorded code hash;
- all seven distinct member signers are registered and the committee is
  frozen at a four-bond threshold floor;
- members 0--3 are slashed exactly once and members 4--6 retain their bonds;
- every member and verifier signature recovers to the registered address;
- every evidence digest is consumed on chain;
- each scenario emits four member-slash events, the expected number of package
  events, one exact reward withdrawal, and one exact treasury withdrawal;
- each scenario realizes four bonds of covered loss, four configured caller
  rewards, the corresponding treasury amount, three temporarily remaining
  bonds, and a zero post-attack current certificate;
- the exact caller reward covers the independently observed gas cost of all
  slash transactions plus reward withdrawal in every mode;
- the terminal state is checked at the recorded historical snapshot block, so
  later committee settlement cannot rewrite the measured result; and
- the result continues to declare controlled keys, non-production status, and
  no independent operators.

Expected terminal markers:

```text
PHASE2_PUBLIC_RECEIPTS=PASS
PHASE2_SOURCE_AND_DEPLOYMENT_INPUT=PASS
PHASE2_MEMBER_AND_VERIFIER_SIGNATURES=PASS
PHASE2_SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS
PHASE2_EXACT_REWARD_AND_TREASURY_WITHDRAWAL=PASS
PHASE2_REWARD_GAS_COVERAGE=PASS
PHASE2_SCOPE_GUARDS=PASS
```
