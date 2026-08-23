# Start this host's operators from their own secret files and the public
# committee bundle. Replay protection persists to disk, so a re-run needs a fresh
# run id (run_two_host does that by default); this script does not wipe the nonce
# logs, which are append-only evidence.
param([Parameter(Mandatory=$true)][ValidateSet("host1","host2")][string]$HostId)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$cfg = Get-Content (Join-Path $Root "config\$HostId.v3.json") -Raw | ConvertFrom-Json
$public = Join-Path $Root "config\committee.public.v3.json"
$server = Join-Path $Root "src\ptr_v3\operator_server.py"
$secretDir = Join-Path $Root "secrets\$HostId"
$resultsDir = Join-Path $Root "results\$HostId"

if (-not (Test-Path $public)) {
    throw "public committee bundle missing: $public. Run the setup step for this host first."
}
foreach ($op in $cfg.operators) {
    $secret = Join-Path $secretDir "operator-$op.secret.json"
    if (-not (Test-Path $secret)) {
        throw "secret file missing: $secret. This host has not been dealt its keys."
    }
}
# A host must not hold secret files for operators it does not run.
$foreign = Get-ChildItem $secretDir -Filter "operator-*.secret.json" -ErrorAction SilentlyContinue |
    Where-Object { [int]($_.BaseName -replace '\D','') -notin $cfg.operators }
if ($foreign) {
    throw "this host holds foreign secret files: $($foreign.Name -join ', '). Key isolation is violated."
}

New-Item -ItemType Directory -Force -Path $resultsDir | Out-Null

# Idempotent: a port already serving the correct operator is left running; only a
# wrong or dead port is cleared and (re)started. This stops a re-invocation from
# killing healthy operators or leaving a stale process that would skew the outage
# test.
$started = @()
$reused = @()
foreach ($op in $cfg.operators) {
    $port = $cfg.ports."$op"
    $correct = $false
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2
        if ($h.operator_id -eq $op -and $h.host_id -eq $HostId) { $correct = $true }
    } catch { }
    if ($correct) {
        $reused += $op
        Write-Host "REUSED operator=$op port=$port (already correct)"
        continue
    }
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }
    $secret = Join-Path $secretDir "operator-$op.secret.json"
    $transcript = Join-Path $resultsDir "operator-$op.transcript.jsonl"
    $nonceLog = Join-Path $resultsDir "operator-$op.nonces.log"
    Start-Process -FilePath "py" -ArgumentList "-3", $server,
        "--operator-id", $op, "--bind", $cfg.bind, "--port", $port,
        "--secret", $secret, "--public", $public,
        "--transcript", $transcript, "--nonce-log", $nonceLog -WindowStyle Hidden
    $started += $op
    Write-Host "STARTED operator=$op port=$port bind=$($cfg.bind)"
}
if ($started.Count -gt 0) { Start-Sleep -Seconds 4 }

$ready = 0
foreach ($op in $cfg.operators) {
    $port = $cfg.ports."$op"
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 3
        if ($h.host_id -ne $HostId) { throw "operator $op reports host $($h.host_id)" }
        if ($h.operator_id -ne $op) { throw "port $port serves operator $($h.operator_id), expected $op" }
        $ready++
    } catch { Write-Host "OPERATOR_DOWN=$op port=$port" }
}
Write-Host "REUSED=$($reused.Count) STARTED=$($started.Count)"
Write-Host "$($HostId.ToUpper())_OPERATORS_READY=$ready"
if ($ready -ne $cfg.operators.Count) { throw "not all operators are ready" }
