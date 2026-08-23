param([Parameter(Mandatory=$true)][ValidateSet("host1","host2")][string]$HostId)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$cfg = Get-Content (Join-Path $Root "config\$HostId.v3.json") -Raw | ConvertFrom-Json
foreach ($op in $cfg.operators) {
    $port = $cfg.ports."$op"
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "STOPPED operator=$op port=$port"
    }
}