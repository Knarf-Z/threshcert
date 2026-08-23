$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& py -3.11 .\scripts\verify_code_manifest.py
if ($LASTEXITCODE -ne 0) { throw "code-to-manifest fidelity failed" }

Write-Host "CODE_FIDELITY_VERIFICATION=PASS"
