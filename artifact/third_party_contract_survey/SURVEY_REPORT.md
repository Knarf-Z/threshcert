# Third-party direct-closed-contract survey

## Scope

This survey applies the reusable layers of the paper's deployment-admission
method to third-party Ethereum mainnet contracts. The eight-subject cohort was
frozen before screening at block 25,658,467, block hash
`0x5fdd73a6e17f7190c3afca016c1bb67a67266ccac791dbac502575d2a4aa1b11`.
Addresses and the ex ante inclusion rule are in
`cohort.ethereum-mainnet.v1.json`.

The cohort is a purposive stress sample across Ethereum deposits, SSV,
EigenLayer, Lido, and Rocket Pool. It is not random and supports no ecosystem
prevalence estimate. Proxy implementations are not counted as additional
subjects.

## Method and status meanings

The reusable screen checks pinned-chain provenance, deployment identity when a
verified creation transaction is available, runtime-template identity modulo
declared relocations, executable forbidden opcodes, EIP-1967 slots, the
EIP-1167 fingerprint, and ABI availability.

`commonStaticScreen=PASS` means that every reusable provenance, identity,
template, and direct-control-flow check passed. `INCOMPLETE` means that none of
those checks failed but at least one input was unavailable. `FAIL` means that
at least one reusable condition was affirmatively violated.

`closedContractAdmission` is strictly stronger. It also requires a
contract-specific mutating-entry whitelist and machine-checkable evidence for
entry closure, payer separation, payment preservation, backward realization,
terminal equivalence, and offset closure. Missing evidence fails closed. No
status in this survey is a claim that a contract or protocol is insecure.

## Frozen result

| Subject | Common static screen | Main reusable-layer reason | Full admission |
|---|---|---|---|
| Ethereum Deposit Contract | PASS | all common checks passed | FAIL_CLOSED: semantic evidence absent |
| SSV Network | FAIL | EIP-1967 implementation slot and `DELEGATECALL` | FAIL_CLOSED |
| EigenLayer DelegationManager | FAIL | EIP-1967 implementation slot and `DELEGATECALL` | FAIL_CLOSED |
| Lido StakingRouter | FAIL | EIP-1967 implementation slot and `DELEGATECALL` | FAIL_CLOSED |
| Lido DepositSecurityModule | INCOMPLETE | verified template/deployment identity unavailable from the queried Sourcify record | FAIL_CLOSED |
| Lido ValidatorStrikes | FAIL | EIP-1967 implementation slot and `DELEGATECALL`; template unavailable | FAIL_CLOSED |
| Lido Veto Signaling Escrow | FAIL | EIP-1167 minimal proxy and `DELEGATECALL`; template unavailable | FAIL_CLOSED |
| Rocket Pool Auction Manager | FAIL | Sourcify `match` is not an exact creation/runtime template match under the strict checker | FAIL_CLOSED |

Aggregate counts are therefore:

- common static layer: 1 PASS, 6 FAIL, 1 INCOMPLETE;
- ABI inventory: available for 5 of 8 subjects;
- full direct-closed incidence admission: 0 PASS, 8 FAIL_CLOSED;
- explicit `DELEGATECALL` policy failures: 5;
- nonzero EIP-1967 proxy-slot failures: 4;
- EIP-1167 minimal-proxy failures: 1.

The non-self-referential finding is narrow but useful. The checker does not
merely reject every foreign ABI: one third-party contract passes all reusable
static layers. Most sampled protocol-facing subjects, however, expose proxy or
delegate-call structure that falls outside the paper's direct closed-contract
theorem. Even the static-pass candidate cannot be promoted to an economic
incidence certificate without contract-specific semantic evidence.

## Reproduction and integrity

The survey has no package dependencies. From this directory:

```text
node test_screen_contract_v2.mjs
node aggregate_results_v2.mjs
node verify_manifest_v2.mjs
```

The regression suite admits one synthetic baseline and rejects eight tampered
variants. `aggregate.ethereum-mainnet.v2.json` is the canonical aggregate,
with a CSV rendering beside it. `MANIFEST.v2.sha256` fixes the cohort, tools,
records, raw Sourcify responses, derived artifacts, and per-subject results.

## Limitations

- The sample is small and purposive.
- Three queried addresses lacked complete Sourcify v2 verification data at
  collection time; they remain incomplete unless an independent verified
  artifact is supplied.
- The policy deliberately excludes proxy/delegate-call architectures instead
  of recursively proving their implementation and upgrade-authority closure.
- Passing the common static layer does not establish acquisition rights,
  member-borne loss, usable threshold shares, or absence of reimbursement.
- No member reservation price or production economic lower bound is measured.
