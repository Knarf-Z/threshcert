$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run .\setup.ps1 first."
}

New-Item -ItemType Directory -Force -Path "results" | Out-Null

# Remove only known generated files so an in-place upgrade cannot leave stale
# evidence from an earlier run.
$generatedResults = @(
    "results\atomic_bypass_curve.csv",
    "results\atomic_bypass_repetition.csv",
    "results\atomic_bypass_summary.json",
    "results\environment.json",
    "results\evidence_sensitivity.csv",
    "results\evidence_sensitivity_summary.json",
    "results\foundry_test_output.txt",
    "results\foundry_version.txt",
    "results\historical_keyper_sets.csv",
    "results\historical_keyper_sets.json",
    "results\historical_keyper_sets_summary.json",
    "results\longitudinal_audit.csv",
    "results\longitudinal_audit_summary.json",
    "results\pinned_snapshot_audit.csv",
    "results\pinned_snapshot_audit.json",
    "results\pinned_snapshot_audit_summary.json",
    "results\python_test_output.txt",
    "results\replacement_hull_summary.json",
    "results\replacement_hull_tolerance_sweep.csv",
    "results\replacement_hull_trials.csv",
    "results\run_manifest.json"
)
foreach ($generatedResult in $generatedResults) {
    if (Test-Path $generatedResult) {
        Remove-Item -Path $generatedResult -Force
    }
}

function Assert-NativeSuccess {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

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
Assert-NativeSuccess "Environment report"
& $python experiments\longitudinal_audit.py --config config\audit.example.json
Assert-NativeSuccess "Pinned snapshot audit"
& $python experiments\atomic_bypass.py
Assert-NativeSuccess "Atomic bypass experiment"
& $python experiments\replacement_hull.py --repetitions 60
Assert-NativeSuccess "Replacement-hull experiment"
& $python experiments\evidence_sensitivity.py
Assert-NativeSuccess "Evidence-sensitivity experiment"

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
$pythonStatus = "passed_pytest"

$foundryStatus = "not_installed"
$forgeCommand = Get-Command forge -ErrorAction SilentlyContinue
$forge = if ($forgeCommand) {
    $forgeCommand.Source
}
elseif (Test-Path "$env:USERPROFILE\.foundry\bin\forge.exe") {
    "$env:USERPROFILE\.foundry\bin\forge.exe"
}
else {
    $null
}

if ($forge) {
    $forgeVersionLines = & $forge --version 2>&1
    $forgeVersionExitCode = $LASTEXITCODE
    Write-Utf8Lines "results\foundry_version.txt" $forgeVersionLines
    if ($forgeVersionExitCode -ne 0) {
        throw "Foundry version check failed with exit code $forgeVersionExitCode"
    }
    Push-Location contracts
    try {
        $forgeLines = & $forge test -vv 2>&1
        $forgeExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    Write-Utf8Lines "results\foundry_test_output.txt" $forgeLines
    $forgeLines | Write-Host
    if ($forgeExitCode -ne 0) {
        throw "Foundry tests failed with exit code $forgeExitCode"
    }
    $forgeText = $forgeLines -join [Environment]::NewLine
    if ($forgeText -notmatch "\b20 tests passed, 0 failed\b") {
        throw "Foundry test count mismatch; expected 20 passed."
    }
    $foundryStatus = "passed_native"
}

& $python experiments\make_manifest.py `
    --python-status $pythonStatus `
    --foundry-status $foundryStatus
Assert-NativeSuccess "Manifest generation"
& $python experiments\verify_results.py
Assert-NativeSuccess "Manifest verification"
Write-Host "All experiments completed. Results are in $PSScriptRoot\results"
