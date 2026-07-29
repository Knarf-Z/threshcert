# Trace-Then-Slash phase one — RQ2 instance

This repository is the first-stage strong-route artifact for a fixed 4-of-7
committee. Seven distinct accountability keys run on one host. Independent
operators are intentionally deferred.

The mechanism turns a covered premature-share acquisition into a verifiable
loss:

- the member signs a job-bound early-share artifact;
- a configured verifier attests share validity;
- any caller can submit one artifact or an atomic package before release;
- the complete member bond is slashed;
- a non-zero caller reward is accrued automatically; and
- the remainder is accrued to the penalty treasury.

The batch implementation validates the whole package before changing state.
One invalid item therefore rolls back the complete package. Reward and treasury
payments use pull withdrawals so a reverting recipient cannot block slashing.

## Recorded result

The pinned instance uses seven 2 ETH bonds, threshold four, and a 0.1 ETH
caller reward per valid artifact. The recorded local-EVM executions show:

| Acquisition/submission form | Transactions | Realized member loss | Caller reward | Scoped lower bound |
|---|---:|---:|---:|---:|
| Sequential | 4 | 8 ETH | 0.4 ETH | 8 ETH |
| One atomic package | 1 | 8 ETH | 0.4 ETH | 8 ETH |
| Two repeated packages | 2 | 8 ETH | 0.4 ETH | 8 ETH |

The post-attack `currentCertificate()` is zero in all three cases because four
members have been slashed. That value reports that the committee is exhausted;
it does not erase the 8 ETH loss realized by the covered attack.

## Reproduce

Requirements: Node.js 22+ and Python 3.10+.

```bash
python reproduce.py
```

In Windows PowerShell, force the installed Python launcher version if the
Microsoft Store execution alias shadows `python`:

```powershell
py -3.11 .\reproduce.py
```

The command installs pinned dependencies, compiles and type-checks the
contract, runs adversarial tests, executes the three positive scenarios, and
verifies `results/phase1_scenarios.json`.

The expected terminal markers are:

```text
PHASE1_CERTIFICATE=POSITIVE_SCOPED
LOWER_BOUND_WEI=8000000000000000000
SEQUENTIAL_ATOMIC_REPEATED_EQUIVALENCE=PASS
CALLER_REWARD_ACCRUAL=PASS
NO_EXTERNAL_PACKAGE_BOUND_B=PASS
SCOPE_GUARDS=PASS
MANIFEST=PASS
```

Read [SCOPE.md](SCOPE.md) before citing the result. The certificate is scoped
to member-signed public artifacts, verifier validity, timely submission, and
chain liveness. It does not claim production economics or independent
operation.
