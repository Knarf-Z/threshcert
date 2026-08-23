# Upgrade an existing Windows copy to v3

The archive keeps the same top-level folder name, so it can be expanded over
the existing project without deleting the virtual environment.

```powershell
Expand-Archive `
  -Path "$env:USERPROFILE\Downloads\FC_experiment_upgrade_v3.zip" `
  -DestinationPath "D:\paper_project" `
  -Force

Set-Location "D:\paper_project\fc_experiment_upgrade"
Set-ExecutionPolicy -Scope Process Bypass
.\run_all.ps1
```

There is no need to run `setup.ps1` again if `.venv` already exists.
`run_all.ps1` detects Foundry at
`$env:USERPROFILE\.foundry\bin\forge.exe`.

Expected validation:

- 10 Python tests pass.
- 14 Foundry tests pass.
- `results\run_manifest.json` reports `python_status` as `passed_pytest`.
- `results\run_manifest.json` reports `foundry_status` as `passed_native`.

Create a result bundle after the run:

```powershell
Compress-Archive `
  -Path ".\results\*" `
  -DestinationPath "$env:USERPROFILE\Downloads\FC_experiment_results_v3.zip" `
  -Force
```
