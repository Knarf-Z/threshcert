$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    & (Join-Path $Root "powershell\Setup-Host1.ps1")
}

$env:PYTHONPATH = Join-Path $Root "src"

Write-Host "Running unit tests..."
& $Python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Unit tests failed." }
Write-Host "UNIT_TESTS=PASS"

Write-Host "Running Host 1 experiment..."
& $Python scripts\run_host1.py --config config\host1.json --canonical results\canonical_result.v2.json --metadata results\run_metadata.v2.json
if ($LASTEXITCODE -ne 0) { throw "Experiment failed." }

Write-Host "Replaying for canonical determinism..."
& $Python scripts\run_host1.py --config config\host1.json --canonical results\replay_canonical.json --metadata results\replay_metadata.json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Replay failed." }
$first = (Get-FileHash results\canonical_result.v2.json -Algorithm SHA256).Hash
$second = (Get-FileHash results\replay_canonical.json -Algorithm SHA256).Hash
Remove-Item results\replay_canonical.json, results\replay_metadata.json -Force
if ($first -ne $second) { throw "Canonical result is not deterministic." }
Write-Host "DETERMINISTIC_CANONICAL_REPLAY=PASS"
Write-Host "CANONICAL_SHA256=$first"

Write-Host "Verifying result..."
& $Python scripts\verify_results.py --canonical results\canonical_result.v2.json
if ($LASTEXITCODE -ne 0) { throw "Result verification failed." }

Write-Host "Building manifest..."
& $Python scripts\build_manifest.py
if ($LASTEXITCODE -ne 0) { throw "Manifest build failed." }

Write-Host "HOST1_RUN=PASS"
