# Run once on host 1 (the dealer). Mints the public committee bundle and this
# host's secret files for operators 1, 3, 5. The dealer seed stays in
# config\dealer_seed.v3.json and is never shipped.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

& py -3 (Join-Path $Root "scripts\deal_keys.py") --host host1
if ($LASTEXITCODE -ne 0) { throw "dealing host 1 keys failed" }

# Host 1 must not carry operators 2, 4, 6, 7's secrets at run time.
$foreign = Get-ChildItem (Join-Path $Root "secrets\host1") -Filter "operator-*.secret.json" |
    Where-Object { [int]($_.BaseName -replace '\D','') -in 2,4,6,7 }
if ($foreign) { throw "host 1 secret dir contains remote operator secrets: $($foreign.Name -join ', ')" }

Write-Host "HOST1_SETUP=OK"
Write-Host "Secrets: secrets\host1\operator-1,3,5.secret.json"
Write-Host "Public : config\committee.public.v3.json"
