$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Run Setup-Host1.ps1 first." }
$env:PYTHONPATH = Join-Path $Root "src"
& $Python scripts\verify_results.py --canonical results\canonical_result.v2.json
if ($LASTEXITCODE -ne 0) { throw "Result verification failed." }
& $Python scripts\verify_manifest.py
if ($LASTEXITCODE -ne 0) { throw "Manifest verification failed." }
Write-Host "HOST1_VERIFY=PASS"
