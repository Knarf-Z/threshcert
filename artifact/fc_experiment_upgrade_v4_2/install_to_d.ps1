$ErrorActionPreference = "Stop"
$source = $PSScriptRoot
$destination = "D:\paper_project\fc_experiment_upgrade"

if (-not (Test-Path "D:\")) {
    throw "Drive D: was not found."
}

$resolvedSource = (Resolve-Path $source).Path.TrimEnd("\")
$resolvedDestination = [System.IO.Path]::GetFullPath($destination).TrimEnd("\")
if ($resolvedSource -ieq $resolvedDestination) {
    Write-Host "Project is already installed at $destination"
    exit 0
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Path "$source\*" -Destination $destination -Recurse -Force
Write-Host "Installed to $destination"
