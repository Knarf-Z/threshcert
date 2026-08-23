# Run as Administrator on host 2. Opens only the four operator ports, and only
# to host 1's address.
param([Parameter(Mandatory=$true)][string]$Host1Address)
$ErrorActionPreference = "Stop"
foreach ($port in 8702, 8704, 8706, 8707) {
    $name = "PTR v3 operator $port"
    Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $port -RemoteAddress $Host1Address | Out-Null
    Write-Host "FIREWALL_ALLOW port=$port from=$Host1Address"
}