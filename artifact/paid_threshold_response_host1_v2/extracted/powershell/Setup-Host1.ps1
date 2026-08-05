$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "ROOT=$Root"

$py = Get-Command py -ErrorAction SilentlyContinue
if ($null -eq $py) {
    throw "Python launcher 'py' was not found. Install Python 3.11 or newer first."
}

$version = & py -3 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Host "PYTHON_VERSION=$version"

if (-not (Test-Path ".venv")) {
    & py -3 -m venv .venv
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
& $VenvPython -c "import sys; assert sys.version_info >= (3, 11); print('VENV_READY=' + sys.executable)"

Write-Host "No external Python packages are required."
Write-Host "HOST1_SETUP=PASS"
