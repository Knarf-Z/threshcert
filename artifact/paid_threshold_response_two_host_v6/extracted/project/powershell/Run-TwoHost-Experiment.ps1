# Run on host 1. Drives the full two-host experiment end to end. The only manual
# actions are physical: stop host 2's operators when asked, then restart them.
# This script waits for those states by polling host 2's /health rather than by a
# blind Enter, so the recovery phase can no longer start before host 2 is back.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "src"

$topology = Get-Content (Join-Path $Root "config\topology.v3.json") -Raw | ConvertFrom-Json
$host2cfg = Get-Content (Join-Path $Root "config\host2.v3.json") -Raw | ConvertFrom-Json
$host2addr = $topology.host2.address
$host2ops = @($host2cfg.operators)

function Get-RemoteReadyCount {
    $ready = 0
    foreach ($op in $host2ops) {
        $port = $host2cfg.ports."$op"
        try {
            $h = Invoke-RestMethod "http://${host2addr}:$port/health" -TimeoutSec 2
            if ($h.host_id -eq "host2" -and $h.operator_id -eq $op) { $ready++ }
        } catch { }
    }
    return $ready
}

function Wait-RemoteState {
    param(
        [Parameter(Mandatory = $true)][int]$Target,   # desired ready count
        [Parameter(Mandatory = $true)][string]$Banner, # WAITING_FOR_HOST2_*
        [Parameter(Mandatory = $true)][string]$Label,  # REMOTE_*_READY / REMOTE_STILL_UP
        [int]$TimeoutSec = 600
    )
    $total = $host2ops.Count
    Write-Host $Banner
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ($true) {
        $n = Get-RemoteReadyCount
        Write-Host "$Label=$n/$total"
        if ($n -eq $Target) { return }
        if ((Get-Date) -gt $deadline) { throw "$Banner timed out after ${TimeoutSec}s (stuck at $n/$total)" }
        Start-Sleep -Seconds 3
    }
}

Write-Host "Running unit tests..."
& py -3 -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "unit tests failed" }
Write-Host "UNIT_TESTS=PASS"

& py -3.11 .\scripts\extract_restricted_source_inventory.py
if ($LASTEXITCODE -ne 0) { throw "restricted source inventory extraction failed" }

& py -3.11 .\scripts\compiler_bytecode_crosscheck.py
if ($LASTEXITCODE -ne 0) { throw "CPython bytecode cross-check failed" }

& py -3.11 .\scripts\source_coverage_kernel.py
if ($LASTEXITCODE -ne 0) { throw "RSP-V6 source proof failed" }

if (-not (Test-Path (Join-Path $Root "config\committee.public.v3.json"))) {
    Write-Host "Public bundle missing; running the host-1 key ceremony..."
    & (Join-Path $Root "powershell\Setup-Host1.ps1")
    if ($LASTEXITCODE -ne 0) { throw "host 1 setup failed" }
}

& (Join-Path $Root "powershell\Start-Operators.ps1") -HostId host1
& (Join-Path $Root "powershell\Test-Host2-Connectivity.ps1")

Write-Host "Running groups A, B, E and the fault matrix..."
& py -3 scripts\run_two_host.py
if ($LASTEXITCODE -ne 0) { throw "main experiment failed" }

# --- outage: wait until host 2 is actually down, then run C and D -------------
Write-Host ""
Write-Host "STOP host 2's operators now (on host 2: .\powershell\Stop-Operators.ps1 -HostId host2)."
Wait-RemoteState -Target 0 -Banner "WAITING_FOR_HOST2_OUTAGE" -Label "REMOTE_STILL_UP"
& py -3 scripts\run_outage_test.py
if ($LASTEXITCODE -ne 0) { throw "outage test failed" }

# --- recovery: wait until all four remote operators are back, then run --------
Write-Host ""
Write-Host "RESTART host 2's operators now (on host 2: .\powershell\Start-Operators.ps1 -HostId host2)."
Wait-RemoteState -Target $host2ops.Count -Banner "WAITING_FOR_HOST2_RECOVERY" -Label "REMOTE_RECOVERY_READY"
& (Join-Path $Root "powershell\Start-Operators.ps1") -HostId host1   # idempotent: reuses live host-1 operators
& py -3 scripts\run_outage_test.py --recovery --output results\recovery_result.v3.json
if ($LASTEXITCODE -ne 0) { throw "recovery test failed" }

Write-Host ""
& py -3 scripts\verify_two_host.py
if ($LASTEXITCODE -ne 0) { throw "verification failed" }
Write-Host "TWO_HOST_RUN=PASS"
