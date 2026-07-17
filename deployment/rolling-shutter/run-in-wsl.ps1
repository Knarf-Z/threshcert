$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$linuxPath = (wsl wslpath -a $here).Trim()
if (-not $linuxPath) { throw "WSL could not translate the project path" }
wsl bash -lc "cd '$linuxPath' && ./setup-seven-4of7.sh"
if ($LASTEXITCODE -ne 0) { throw "Rolling Shutter setup failed with exit code $LASTEXITCODE" }
