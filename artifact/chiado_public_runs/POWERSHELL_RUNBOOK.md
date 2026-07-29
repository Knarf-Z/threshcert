# PowerShell runbook

Run every command from a fresh extraction of this package. Do not overwrite a
previous public run.

## 1. Local validation

```powershell
Set-Location ".\chiado_public_runs"

$env:NPM_CONFIG_CACHE = "$PWD\.runtime\npm-cache"
$env:NPM_CONFIG_LOGS_DIR = "$PWD\.runtime\npm-logs"

npm.cmd ci --no-audit --no-fund
npm.cmd run ready
```

Expected local result:

```text
16 passing (16 nodejs)
```

`No contracts to compile` is normal when the compilation cache is current.

## 2. Public Chiado deployment

The global Hardhat production keystore must contain:

```text
CHIADO_RPC_URL
CHIADO_DEPLOYER_PRIVATE_KEY
```

Use `https://rpc.chiadochain.net` as the deployment RPC. Never paste the
private key into a PowerShell variable or project file.

```powershell
$env:PHASE2_EXECUTE = "I_UNDERSTAND_PUBLIC_TRANSACTIONS"
$env:PHASE2_BOND_NATIVE = "0.002"
$env:PHASE2_CALLER_REWARD_NATIVE = "0.0005"
$env:PHASE2_GAS_RESERVE_NATIVE = "0.02"
$env:PHASE2_MAX_TOTAL_NATIVE = "0.1"

Start-Transcript -Path ".\phase2-deploy.log" -Append
npm.cmd run phase2:deploy
Stop-Transcript
```

Do not close PowerShell while the three scenarios are running. A successful
run ends with:

```text
PHASE2_PUBLIC_PACKAGE_INVARIANCE=PASS
PHASE2_REWARD_GAS_COVERAGE=PASS
```

If the gas-coverage marker fails, do not describe that run as cost-covered.
Keep its public receipts, increase `PHASE2_CALLER_REWARD_NATIVE`, and execute a
new run in a new extraction.

## 3. Independent archive-RPC verification

The Gnosis documentation lists `https://rpc.chiado.gnosis.gateway.fm` as the
Chiado archive RPC, distinct from the deployment endpoint.

```powershell
$env:CHIADO_VERIFY_RPC_URL = "https://rpc.chiado.gnosis.gateway.fm"
npm.cmd run phase2:verify 2>&1 |
    Tee-Object -FilePath ".\phase2-verify.log"
```

The verifier refuses to fall back to the deployment endpoint. All seven PASS
markers in `VERIFICATION.md` must appear.

## 4. Build the reproducibility manifest

```powershell
npm.cmd run manifest:build
npm.cmd run manifest:check
```

Expected final marker:

```text
MANIFEST=PASS
```

## 5. Recover unslashed bonds after the release window

Do not run settlement before the UTC release times recorded in
`results\phase2_chiado.json`.

```powershell
$env:PHASE2_SETTLE = "I_UNDERSTAND_PUBLIC_SETTLEMENT"
npm.cmd run phase2:settle
npm.cmd run manifest:build
npm.cmd run manifest:check
```

Successful settlement ends with:

```text
PHASE2_REMAINING_BONDS_RECOVERED=PASS
```
