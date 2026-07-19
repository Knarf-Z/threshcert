# Completed Chiado public run

This directory contains the returned records from the completed controlled
experiment on Gnosis Chiado (chain ID 10200).

## Public identifiers

- Contract: [`0x3C16dd5689D67d51c076fe80CB7189041c107721`](https://gnosis-chiado.blockscout.com/address/0x3C16dd5689D67d51c076fe80CB7189041c107721)
- Deployment transaction: [`0x0fbbe151dfb855f568e354dd66a98c687379fbe9df95c08a81a4f06d94dac21a`](https://gnosis-chiado.blockscout.com/tx/0x0fbbe151dfb855f568e354dd66a98c687379fbe9df95c08a81a4f06d94dac21a)
- Release-job transaction: [`0xec6ecd8fc4a7df5bbf68e5ee8ff408ad7f6e0ed9d0a179cc3068448042fbcaa6`](https://gnosis-chiado.blockscout.com/tx/0xec6ecd8fc4a7df5bbf68e5ee8ff408ad7f6e0ed9d0a179cc3068448042fbcaa6)
- Release job: `0xe33257d2784a1695ae1e14d9cc5b4852ff78debe7fdbd60b6facd939895b636f`
- Slashing transaction: [`0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`](https://gnosis-chiado.blockscout.com/tx/0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd)

## Cross-record result

- Seven distinct Keyper process addresses were registered and the committee
  was frozen at threshold four.
- All nine deployment/registration/freeze transactions succeeded.
- Total bond was `7,000,000,000,000` wei; the initial four-member certificate
  was `4,000,000,000,000` wei.
- The pinned Rolling Shutter v1.4.4 exporter validated seven BLS shares, seven
  native Keyper signatures, the stored aggregate key, and equality with a
  four-share reconstruction.
- Member 0's validated share was observed 5,350 seconds before the public
  release time.
- The slashing transaction succeeded at block 22,111,234 and reduced the
  certificate to `3,000,000,000,000` wei.

The automated checks in `tests/test_bundle_integrity.py` verify these statements
directly from `deployment-chiado.json`, `job-chiado.json`,
`../evidence/shutter-evidence.json`, `slashing-chiado.json`, and the exported
Keyper set.

## Machine-readable certificate

`../certificates/chiado-execution-certificate.json` binds these run records,
the contract, the pinned evidence exporter, the exported Keyper set, and the
live-chain verifier by SHA-256. It recomputes the exact four-smallest-bonds
values as `4,000,000,000,000` wei before slashing and
`3,000,000,000,000` wei after slashing. Verify it from `deployment/` with:

```bash
python scripts/verify_chiado_certificate.py
```

The certificate class is `controlled-public-testnet-threshold-cover`. The JSON
itself records `productionShutterCertificate: NOT_CERTIFIED`, so the positive
testnet result cannot be silently relabeled as a production resistance claim.

## Boundary

This is a verifier-gated, single-host, controlled testnet experiment. It is not
native on-chain BLS verification, a production deployment, or evidence of seven
independently governed operators. The disclosed Shutter identity preimage is a
controlled release identifier and is not a wallet private key.
