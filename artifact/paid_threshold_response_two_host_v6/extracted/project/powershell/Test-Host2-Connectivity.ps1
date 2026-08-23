# Run on host 1. Confirms every remote operator answers and reports the host the
# registry expects.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$topology = Get-Content (Join-Path $Root "config\topology.v3.json") -Raw | ConvertFrom-Json
$cfg = Get-Content (Join-Path $Root "config\host2.v3.json") -Raw | ConvertFrom-Json
$address = $topology.host2.address
if ($address -eq "127.0.0.1" -or $address -eq "localhost") {
    Write-Host "TOPOLOGY_STILL_LOOPBACK=true -- config\topology.v3.json has not been pointed at host 2"
}

$env:PYTHONPATH = Join-Path $Root "src"
$localDigest = & py -3 -c "import sys; sys.path.insert(0, r'$Root\src'); from ptr_v3.operator_server import MACHINE_DIGEST; print(MACHINE_DIGEST)"

$ok = 0
$distinct = 0
foreach ($op in $cfg.operators) {
    $port = $cfg.ports."$op"
    try {
        $h = Invoke-RestMethod "http://${address}:$port/health" -TimeoutSec 5
        if ($h.host_id -ne "host2") { throw "operator $op reports host $($h.host_id)" }
        if (-not $h.machine_digest) { throw "operator $op reports no machine fingerprint (stale bundle?)" }
        if ($h.machine_digest -ne $localDigest) { $distinct++ }
        Write-Host "REMOTE_OK operator=$op port=$port routes=$($h.served_routes -join ',')"
        $ok++
    } catch { Write-Host "REMOTE_FAIL operator=$op port=$port $_" }
}
Write-Host "REMOTE_CONNECTIVITY=$(if ($ok -eq $cfg.operators.Count) { 'PASS' } else { 'FAIL' })"
Write-Host "REMOTE_MACHINE_DISTINCT=$distinct/$($cfg.operators.Count)"
if ($ok -ne $cfg.operators.Count) { throw "host 2 is not fully reachable" }
if ($distinct -ne $cfg.operators.Count) {
    Write-Host "WARNING: host 2's operators report this machine's own fingerprint. The run will"
    Write-Host "         complete but the separation witness will refuse the two-host claim."
}