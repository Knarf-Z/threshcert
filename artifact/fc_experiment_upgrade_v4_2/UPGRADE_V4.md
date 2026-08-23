# Upgrade an existing Windows copy to v4

The archive keeps the same top-level folder name. It can be expanded over the
existing project while retaining `.venv`.

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\FC_experiment_upgrade_v4_1.zip" `
  -DestinationPath "D:\paper_project" `
  -Force

Set-Location "D:\paper_project\fc_experiment_upgrade"
Set-ExecutionPolicy -Scope Process Bypass
.\run_all.ps1
```

Expected validation:

- 17 Python tests pass.
- 20 Foundry tests pass.
- `results\run_manifest.json` reports `passed_pytest`.
- If Foundry is installed, it reports `passed_native`.

Then run the real Gnosis historical audit:

```powershell
.\run_live_audit.ps1
```

If the public endpoint rejects the request, supply another archival Gnosis RPC
without saving it into the package:

```powershell
.\run_live_audit.ps1 -RpcUrl "https://YOUR-GNOSIS-RPC"
```

The important output is
`results\historical_keyper_sets_summary.json`. A successful run should verify
the history of 11 committee configurations while leaving the longitudinal
certificate claim `false`, because period-matched public resistance evidence
was retained only for set 10.

Create the result bundle:

```powershell
Compress-Archive `
  -Path ".\results\*" `
  -DestinationPath "$env:USERPROFILE\Downloads\FC_experiment_results_v4.zip" `
  -Force
```
