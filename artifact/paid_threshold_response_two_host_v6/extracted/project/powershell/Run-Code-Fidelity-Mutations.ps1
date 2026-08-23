$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& py -3.11 .\scripts\run_code_manifest_mutations.py
if ($LASTEXITCODE -ne 0) { throw "code fidelity mutation matrix failed" }

Write-Host "CODE_FIDELITY_MUTATIONS=PASS"
