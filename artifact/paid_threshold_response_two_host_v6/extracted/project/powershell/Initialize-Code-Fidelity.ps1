$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& py -3.11 .\scripts\build_code_manifest.py
if ($LASTEXITCODE -ne 0) { throw "code manifest freeze failed" }

& py -3.11 .\scripts\verify_code_manifest.py
if ($LASTEXITCODE -ne 0) { throw "fresh code manifest does not verify" }

Write-Host "CODE_FIDELITY_INITIALIZATION=PASS"
