param(
    [string]$RpcUrl = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Virtual environment not found. Run .\setup.ps1 first."
}
if (-not (Test-Path ".\results\run_manifest.json")) {
    throw "Run .\run_all.ps1 before the live historical audit."
}

$manifest = Get-Content ".\results\run_manifest.json" -Raw |
    ConvertFrom-Json
$pythonStatus = $manifest.python_status
$foundryStatus = $manifest.foundry_status
$configPath = ".\config\audit.example.json"
$temporaryConfig = $null

try {
    if ($RpcUrl) {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        $config.rpc_url = $RpcUrl
        $temporaryConfig = Join-Path `
            ([System.IO.Path]::GetTempPath()) `
            ("fc-audit-" + [guid]::NewGuid().ToString() + ".json")
        [System.IO.File]::WriteAllText(
            $temporaryConfig,
            ($config | ConvertTo-Json -Depth 20),
            [System.Text.UTF8Encoding]::new($false)
        )
        $configPath = $temporaryConfig
    }

    & $python experiments\longitudinal_audit.py `
        --config $configPath `
        --live
    if ($LASTEXITCODE -ne 0) {
        throw "Live historical audit failed with exit code $LASTEXITCODE"
    }
}
finally {
    if ($temporaryConfig -and (Test-Path $temporaryConfig)) {
        Remove-Item -Path $temporaryConfig -Force
    }
}

& $python experiments\make_manifest.py `
    --python-status $pythonStatus `
    --foundry-status $foundryStatus
if ($LASTEXITCODE -ne 0) {
    throw "Manifest regeneration failed with exit code $LASTEXITCODE"
}
& $python experiments\verify_results.py
if ($LASTEXITCODE -ne 0) {
    throw "Manifest verification failed with exit code $LASTEXITCODE"
}

$summary = Get-Content `
    ".\results\historical_keyper_sets_summary.json" `
    -Raw |
    ConvertFrom-Json

Write-Host "Live historical audit complete."
Write-Host "Sets audited: $($summary.sets_audited)"
Write-Host `
    "Longitudinal committee claim: $($summary.supports_longitudinal_committee_claim)"
Write-Host `
    "Longitudinal certificate claim: $($summary.supports_longitudinal_certificate_claim)"
