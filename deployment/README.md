# ThreshCert real-deployment pilot

This bundle adds a real, seven-process, 4-of-7 Rolling Shutter deployment and a public Chiado
verifier-gated slashing transaction to the existing Python experiments. It pins Rolling Shutter
`v1.4.4` at commit `d143fffcf51f85b30375134d2d29756417f333b9`.

It does **not** claim seven independent organizations: all seven Keyper processes run on one machine.
It also does not claim native on-chain BLS verification; see `SECURITY.md`.

## Requirements

- Windows 10/11 with Docker Desktop and WSL integration
- WSL with `bash`, `git`, `python3`, and `openssl`
- Node.js 22 or newer and npm in the PyCharm terminal
- a newly generated Chiado-only deployer and a separate verifier account
- enough Chiado xDAI to fund deployment, seven bonds, and transactions

## 1. Deterministic contract checks

From the PyCharm PowerShell terminal:

```powershell
npm ci
npm run typecheck
npm test
```

Expected result: seven passing contract tests.

## 2. Start the real 7-process, 4-of-7 Shutter network

Still from the PyCharm PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\rolling-shutter\run-in-wsl.ps1
```

This clones the pinned official source, builds the official image, generates fresh P2P/Keyper keys,
starts seven validator and seven Keyper processes, performs DKG, and writes
`runtime/keyper-set.json`. No runtime private key is added to the artifact.

## 3. Deploy the bonded committee to Chiado

Set secrets only in the current PowerShell process:

```powershell
$env:CHIADO_RPC_URL = "https://rpc.chiado.gnosis.gateway.fm"
$env:CHIADO_DEPLOYER_PRIVATE_KEY = "0x..."
$env:EVIDENCE_VERIFIER_ADDRESS = "0x..."
$env:PENALTY_TREASURY_ADDRESS = "0x..."
$env:KEYPER_SET_FILE = "runtime/keyper-set.json"
$env:BOND_WEI = "1000000000000"
npm run deploy:chiado
```

The deployment record contains one deployment transaction, seven bond-registration transactions,
and one committee-freeze transaction.

## 4. Register a future Shutter identity, then open the Chiado release job

Register an identity whose local release is ten minutes in the future:

```powershell
wsl bash -lc "cd '$(wsl wslpath -a $PWD)/rolling-shutter' && ./06-register-identity-7.sh"
$identity = Get-Content runtime\identity.json | ConvertFrom-Json
$env:IDENTITY_PREIMAGE_HEX = $identity.identityPreimage
$env:EON = $identity.keyperConfigIndex
$env:RELEASE_DELAY_SECONDS = "1800"
npm run open:chiado
```

The Chiado deadline is deliberately later than the local Shutter trigger. This creates a controlled
premature-share event without claiming that an honest production Keyper misbehaved.

## 5. Export and validate real Shutter evidence

After the local trigger timestamp:

```powershell
wsl bash -lc "cd '$(wsl wslpath -a $PWD)/rolling-shutter' && ./07-export-evidence-7.sh"
```

The exporter refuses output unless all seven shares and all seven native signatures validate, the
stored aggregate key validates, and a reconstruction from four shares equals that stored key.

## 6. Submit the public slashing transaction

```powershell
$env:EVIDENCE_FILE = "evidence/shutter-evidence.json"
$env:EVIDENCE_VERIFIER_PRIVATE_KEY = "0x..."
$env:MEMBER_INDEX = "0"
npm run slash:chiado
```

The generated `results/deployment-chiado.json`, `results/job-chiado.json`,
`evidence/shutter-evidence.json`, and `results/slashing-chiado.json` contain no wallet private keys.
The disclosed Shutter identity preimage is a controlled release identifier, not a wallet secret.

## Recorded public run

The final artifact includes a completed run with the following public results:

- contract: `0x3C16dd5689D67d51c076fe80CB7189041c107721`
- committee: seven Keyper processes, threshold four
- initial certificate: `4,000,000,000,000` wei
- release job: `0xe33257d2784a1695ae1e14d9cc5b4852ff78debe7fdbd60b6facd939895b636f`
- validated evidence: seven shares, valid aggregate key, successful four-share reconstruction
- slashing transaction: `0x26ff2f395c8e4bf6e4f8af170030c5a55e751b652d7e6ab7c9dc30bb422ddabd`
- final certificate: `3,000,000,000,000` wei

See `results/PUBLIC_RUN.md` for explorer links and exact interpretation boundaries.

## Machine-readable execution certificate

The completed run is summarized by
`certificates/chiado-execution-certificate.json`. This is not a copied prose
number: the verifier reconstructs the member bond vectors, computes the sum of
the four smallest values, validates every cross-record identifier, and checks
SHA-256 bindings to the underlying evidence and implementation files.

```powershell
python scripts/verify_chiado_certificate.py
```

Expected final lines:

```text
certificate_after_wei=3000000000000
offline_evidence_binding=PASS
production_shutter_certificate=NOT_CERTIFIED
chiado_execution_certificate=PASS
```

Use `--write` only when deliberately rebuilding the certificate after changing
one of its bound source files. A rebuilt certificate changes its content ID and
requires a corresponding manifest update.

## Independent live-chain verification

Anyone can check the recorded transactions, deployment bytecode, constructor arguments, events,
and current contract state directly against a Chiado RPC endpoint. This command is read-only and
does not load a wallet private key or send a transaction:

```powershell
$env:CHIADO_RPC_URL = "https://rpc.chiado.gnosis.gateway.fm"
npm run verify:chiado:live
```

Expected final line: `chiado_live_verification=PASS`.
