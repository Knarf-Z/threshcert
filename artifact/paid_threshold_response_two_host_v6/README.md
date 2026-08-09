# Proved restricted-source two-host evidence (V6)

This module publishes the final public evidence from a controlled 4-of-7
threshold-ElGamal experiment executed across two physical Windows hosts. It
certifies the named acquirer's exact net outflow as 10 inside the declared
finite service language. It does not claim deployment-wide route closure,
independent economic ownership of all shares, hardware non-exportability,
secure erasure, operating-system integrity, or a measured bribery price.

The retained `ptr_v3` Python namespace, `*.v3.json` filenames, and
`ptr-two-host/v5` wire protocol are compatibility surfaces. V6 changes the
source-proof layer and result schemas; Host 2 did not require another protocol
upgrade.

## Frozen packages

```text
frozen/two_host_v6_final_evidence_20260809.zip
frozen/ptr_code_fidelity_evidence_20260809_114201.zip
verify_two_host_v6.mjs
```

Pinned identities:

```text
execution evidence SHA-256  2de5e3b7ec8ae38e25fc745ac5a2988f62e430e255f6fdce9784001f357e3d84
code fidelity SHA-256       d242af878488bf7cda63cbb076a403d36e4734f615a3374ff94dd329d5eeabca
code manifest identity      49dcddf87ffb94654eb1d5788bd132600b2d2c63baccfee36d2552a1c5c0b2f2
canonical result SHA-256    61ce2f1573154ebbcf21b854e9f9cc0bd831530b8acd3c4bc8c5a101dc231fe5
source proof result         3f770950d0a6f22be62d987c66f6fbeefe6645651000d6f22bb06e14db65b02d
end-to-end result           5034a4864bbba2732d668cd55797bd76a7780224f15d808a670e4fc693dff1f2
```

## Strong-route source proof

`RESTRICTED_SOURCE_SOUNDNESS.md` defines RSP-V6: the accepted Python module
closure, privileged operations, forbidden constructs, trace events, and
transfer rules. The restricted-source-kernel result derives six rule families
and proves source obligations LC1, LC3, LC5, and LC7 in that model. The proof is
not inferred from mutation coverage. The 14/14 mutation result is retained only
as regression evidence.

Two non-identical validation axes accompany the AST proof:

- CPython compiles every frozen source file and a bytecode checker cross-checks
  the confinement of listeners, response sinks, partial production, sensitive
  stores, and threshold delivery. This is not a proof of CPython correctness.
- Bandit 1.9.4 scanned 3,628 lines without suppressions: zero high-, three
  medium-, and three low-severity findings. All six findings have explicit
  dispositions; the report is not represented as an all-green static proof.

The semantic repair behind V6 keeps reconstructed plaintext in a candidate
variable until the threshold, commitment, and exact-buyer guards all pass. Only
then is usable plaintext assigned to the deliverable outcome.

## Checked claims

The standalone Node verifier recomputes or checks:

- both outer archive digests, all public manifest entries, the privacy boundary,
  58 pinned source files, and the complete result-to-result hash chain;
- exact equality between the recorded route set and all 840 ordered choices of
  the first four distinct responders, stopping after the fourth response;
- a certified status/floor pair, ledger-derived lower bound, and realized exact
  value, all with value 10; the 24 minimizing routes are also checked;
- the RSP-V6 proof status, all six derived rule families, four proved source
  obligations, 14 caught source mutations, and the 17-file source inventory;
- the independent CPython-bytecode and Bandit evidence, including raw severity,
  line-count, finding-count, and no-suppression metrics;
- sealed component coverage, payment-potential checks, six code-manifest
  mutations, fail-closed outage, and successful recovery; and
- byte identity of the proof results shared by the execution and code-fidelity
  packages.

Run from the repository root:

```text
node artifact/paid_threshold_response_two_host_v6/verify_two_host_v6.mjs
```

Expected final line:

```text
TWO_HOST_V6_PUBLIC_VERIFICATION=PASS
```

No secret share, real topology address, nonce log, cache, backup, or private
Host 2 package is included.
