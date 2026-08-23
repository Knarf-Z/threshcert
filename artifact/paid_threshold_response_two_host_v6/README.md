# Paid threshold response two-host V6 public artifact

This directory publishes the privacy-scrubbed public release of the controlled
two-host V6 integration experiment. It is supplementary historical evidence;
it is not the v16 process-level OPE certificate and it is not a production
attacker-cost measurement.

The public archive contains the frozen Python source, PowerShell runners,
tests, non-secret configuration templates, canonical results, mutation
matrices, and certificate checkers. The original export procedure excludes
operator secret shares, the dealer seed, actual LAN addresses, replay logs,
private machine metadata, failed runs, and patch backups.

Verify the frozen archive from the repository root with Python 3.11 or newer:

```bash
python artifact/paid_threshold_response_two_host_v6/extracted/project/scripts/export_public_release.py --verify-only artifact/paid_threshold_response_two_host_v6/frozen/two_host_execution_evidence.v68.public.zip
```

Expected output includes `PUBLIC_RELEASE=PASS` and this digest:

```text
2DE5E3B7EC8AE38E25FC745AC5A2988F62E430E255F6FDCE9784001F357E3D84
```

Run the source-level test suite through the public-layout adapter with:

```bash
python artifact/paid_threshold_response_two_host_v6/run_public_tests.py
```

The frozen ZIP intentionally stores public result objects beside `project/`.
The adapter creates a disposable tree and places the untrusted source inventory
where the original tests expect it; it does not alter the frozen archive.
The certified value of 10 applies only to the declared finite first-four route
language and the recorded controlled ledger. Deployment-wide route closure,
operating-system integrity, independent economic operators, and a measured
acquisition price are outside scope. See `extracted/project/README.md` and
`extracted/project/RESTRICTED_SOURCE_SOUNDNESS.md` for the complete boundary.
