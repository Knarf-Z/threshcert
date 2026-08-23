$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run .\setup.ps1 first."
}
if (-not (Test-Path ".\results\run_manifest.json")) {
    throw "Existing run manifest not found."
}
if (-not (Test-Path ".\results\historical_keyper_sets_summary.json")) {
    throw "Live historical results not found; run .\run_live_audit.ps1 first."
}

$previousManifest = Get-Content ".\results\run_manifest.json" -Raw |
    ConvertFrom-Json
$foundryStatus = $previousManifest.foundry_status

function Write-Utf8Lines {
    param(
        [string]$Path,
        [object[]]$Lines
    )
    [System.IO.File]::WriteAllText(
        (Join-Path $PSScriptRoot $Path),
        ($Lines -join [Environment]::NewLine),
        [System.Text.UTF8Encoding]::new($false)
    )
}

& $python experiments\environment_report.py
if ($LASTEXITCODE -ne 0) {
    throw "Environment report failed with exit code $LASTEXITCODE"
}

$pythonTestLines = & $python -m pytest -q 2>&1
$pythonTestExitCode = $LASTEXITCODE
Write-Utf8Lines "results\python_test_output.txt" $pythonTestLines
$pythonTestLines | Write-Host
if ($pythonTestExitCode -ne 0) {
    throw "Python tests failed with exit code $pythonTestExitCode"
}
$pythonTestText = $pythonTestLines -join [Environment]::NewLine
if ($pythonTestText -notmatch "\b17 passed\b") {
    throw "Python test count mismatch; expected 17 passed."
}

& $python experiments\make_manifest.py `
    --python-status "passed_pytest" `
    --foundry-status $foundryStatus
if ($LASTEXITCODE -ne 0) {
    throw "Manifest regeneration failed with exit code $LASTEXITCODE"
}

& $python experiments\verify_results.py
if ($LASTEXITCODE -ne 0) {
    throw "Manifest verification failed with exit code $LASTEXITCODE"
}

$environment = Get-Content ".\results\environment.json" -Raw |
    ConvertFrom-Json
Write-Host "Metadata repair complete."
Write-Host "Environment package version: $($environment.package_version)"
Write-Host "Historical results preserved."
