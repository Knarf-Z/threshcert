# Paid threshold response: controlled two-host V6 artifact

This artifact instantiates the end-to-end finite-language payment certificate on
a real 4-of-7 threshold ElGamal service split across two physical Windows hosts.
It is an integration experiment, not a bribery-price measurement.

## Certified claim

For the frozen source tree, declared ordered first-four-responder route grammar, buyer, resource,
epoch, and complete experiment ledger, the verifier certifies a named-acquirer
outflow floor of 10 token units. A recorded minimizing execution realizes 10, so
the result is exact inside that finite language.

The claim does not cover deployment-wide routes, operating-system or interpreter
integrity, hardware non-exportability, seven independent economic operators, a
production DKG, or a measured acquisition price.

## What V6 adds

- The public ciphertext contains a context-bound commitment, not expected
  plaintext. The encrypted capability and ElGamal nonce use the operating-system
  CSPRNG in the experiment path.
- Plaintext appears only after four valid Chaum-Pedersen partial decryptions and
  the buyer-delivery guard.
- Every health record and signed partial binds a digest of the five operator
  runtime modules; Host 1 rejects a digest mismatch.
- `RESTRICTED_SOURCE_SOUNDNESS.md` defines the accepted Python fragment, forbidden
  constructs, abstract events, transfer rules, lemmas, and the source-kernel
  soundness theorem. The separate proof kernel checks the exact import closure
  and derives LC1, LC3, LC5, and LC7 inside that restricted source model.
- A second representation checker compiles the same closure without executing it
  and checks recursive CPython bytecode for privileged-operation locations and
  dynamic/native escape names. Bandit 1.9.4 supplies a third-party generic scan;
  its complete JSON report and explicit finding adjudication are public.
- Fourteen source mutations attack routes, sinks, secret flow, dynamic loading,
  process spawning, listeners, lifecycle, plaintext exposure, randomness,
  threshold release, producer uniqueness, and runtime-source binding. They are
  regression tests for proof sensitivity, not the proof of soundness.
- `scripts/verify_end_to_end_certificate.py` recomputes the common source/scope
  binding, sealed contract, payment potential, global ledger, allocation, bypass,
  shared-debit, outage, recovery, and exactness checks. There is no numeric
  fallback when a required object is missing.

## Private Host 2 package

Run on Host 1 after the one-time dealer setup:

```powershell
py -3.11 .\scripts\package_host2.py --output .\dist\host2_bundle.zip
```

The private ZIP contains only Host 2's shares for operators 2, 4, 6, and 7 plus
the public bundle and runtime. Never publish it. On Host 2:

```powershell
Expand-Archive .\host2_bundle.zip -DestinationPath C:\ptr_host2_v5 -Force
cd C:\ptr_host2_v5
.\powershell\Open-Host2-Firewall.ps1 -Host1Address HOST1_LAN_ADDRESS
.\powershell\Start-Operators.ps1 -HostId host2
```

Expect `HOST2_OPERATORS_READY=4`.

## Full physical run

After reviewing and intentionally freezing the manifest:

```powershell
py -3.11 .\scripts\build_code_manifest.py --force
.\powershell\Run-TwoHost-V6-Evidence.ps1
```

The runner checks manifest fidelity, six manifest mutations, the restricted-source proof,
its bytecode cross-check, fourteen source regressions, capability and composition certificates, then starts
the physical experiment. When prompted, stop and restart Host 2's operators for
the outage and recovery phases. The final end-to-end verifier must print:

```text
FINITE_LANGUAGE_PAYMENT_STATUS=CERTIFIED
FINITE_LANGUAGE_PAYMENT_FLOOR=10
FINITE_LANGUAGE_PAYMENT_EXACT=10
END_TO_END_CERTIFICATE=PASS
```

The runner then creates `dist/two_host_execution_evidence.public.zip`. The public
release contains frozen source, tests, non-secret configuration, canonical JSON,
coverage results, outage/recovery evidence, and a complete internal manifest. It
contains no secret share, dealer seed, actual topology address, private metadata,
or replay log. Verify it independently with:

```powershell
py -3.11 .\scripts\export_public_release.py --verify-only .\dist\two_host_execution_evidence.public.zip
```

Export the smaller source-fidelity companion package with:

```powershell
.\powershell\Export-Code-Fidelity-Evidence.ps1 -Destination .\dist
```

## Main evidence objects

- `config/code_manifest.v1.json`: exact frozen file and source-surface binding.
- `RESTRICTED_SOURCE_SOUNDNESS.md`: accepted language, rules, lemmas, and theorem.
- `results/restricted_source_inventory.v2.json`: untrusted extraction inventory.
- `results/source_coverage_kernel.v1.json`: separate restricted-source proof result.
- `results/cpython_bytecode_crosscheck.v1.json`: independent representation check.
- `results/source_coverage_mutation_matrix.v1.json`: fourteen proof-regression checks.
- `results/bandit_report.v1.json` and `results/bandit_adjudication.v1.json`:
  third-party generic scan and complete disposition of its findings.
- `results/coverage_certificate.v3.json`: typed LC0 through LC7 component contract.
- `results/capability_certificate.v3.json`: potential, cheap bypass, and shared
  debit fixtures.
- `results/canonical_result.v3.json`: physical run, ledger, catalog, allocation,
  placement, scope, and runtime-source binding.
- `results/outage_result.v3.json` and `results/recovery_result.v3.json`: fail-closed
  dependency and fresh recovery.
- `results/end_to_end_certificate.v1.json`: combined finite-language certificate.

The theorem applies only to the explicitly accepted source fragment and recorded
runtime bindings. The author-produced proof kernel is separate from the service
but is not third-party replication. Its rules, implementation, assumptions, and
regression corpus are public so a reviewer can audit or replace it. The CPython
bytecode comparison and Bandit report add distinct validation axes; neither
extends the claim to the operating system, interpreter implementation, undeclared
routes, economic independence, or hardware non-exportability.