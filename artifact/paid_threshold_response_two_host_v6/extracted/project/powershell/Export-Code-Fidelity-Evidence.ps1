param(
    [string]$Destination = "$env:USERPROFILE\Desktop"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Required = @(
    ".\config\code_manifest.v1.json",
    ".\config\code_manifest.v1.sha256",
    ".\results\code_manifest_binding.v1.json",
    ".\results\code_manifest_mutation_matrix.v1.json",
    ".\RESTRICTED_SOURCE_SOUNDNESS.md",
    ".\results\restricted_source_inventory.v2.json",
    ".\results\source_coverage_kernel.v1.json",
    ".\results\source_coverage_mutation_matrix.v1.json",
    ".\results\cpython_bytecode_crosscheck.v1.json",
    ".\results\bandit_report.v1.json",
    ".\results\bandit_adjudication.v1.json",
    ".\results\end_to_end_certificate.v1.json",
    ".\scripts\fidelity_core.py",
    ".\scripts\build_code_manifest.py",
    ".\scripts\verify_code_manifest.py",
    ".\scripts\run_code_manifest_mutations.py",
    ".\scripts\extract_restricted_source_inventory.py",
    ".\scripts\compiler_bytecode_crosscheck.py",
    ".\scripts\freeze_restricted_source_policy.py",
    ".\scripts\source_coverage_kernel.py",
    ".\scripts\run_source_coverage_mutations.py",
    ".\scripts\adjudicate_bandit_report.py",
    ".\scripts\verify_end_to_end_certificate.py",
    ".\scripts\export_public_release.py",
    ".\powershell\Run-TwoHost-V6-Evidence.ps1"
)
foreach ($Path in $Required) {
    if (-not (Test-Path $Path)) { throw "missing fidelity evidence file: $Path" }
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stage = Join-Path $env:TEMP "ptr_code_fidelity_$Stamp"
$Zip = Join-Path $Destination "ptr_code_fidelity_evidence_$Stamp.zip"
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "config") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "results") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Stage "powershell") | Out-Null

Copy-Item .\config\code_manifest.v1.json (Join-Path $Stage "config")
Copy-Item .\config\code_manifest.v1.sha256 (Join-Path $Stage "config")
Copy-Item .\results\code_manifest_binding.v1.json (Join-Path $Stage "results")
Copy-Item .\results\code_manifest_mutation_matrix.v1.json (Join-Path $Stage "results")
Copy-Item .\RESTRICTED_SOURCE_SOUNDNESS.md $Stage
Copy-Item .\results\restricted_source_inventory.v2.json (Join-Path $Stage "results")
Copy-Item .\results\source_coverage_kernel.v1.json (Join-Path $Stage "results")
Copy-Item .\results\source_coverage_mutation_matrix.v1.json (Join-Path $Stage "results")
Copy-Item .\results\cpython_bytecode_crosscheck.v1.json (Join-Path $Stage "results")
Copy-Item .\results\bandit_report.v1.json (Join-Path $Stage "results")
Copy-Item .\results\bandit_adjudication.v1.json (Join-Path $Stage "results")
Copy-Item .\results\end_to_end_certificate.v1.json (Join-Path $Stage "results")
Copy-Item .\scripts\fidelity_core.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\build_code_manifest.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\verify_code_manifest.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\run_code_manifest_mutations.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\extract_restricted_source_inventory.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\compiler_bytecode_crosscheck.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\freeze_restricted_source_policy.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\source_coverage_kernel.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\run_source_coverage_mutations.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\adjudicate_bandit_report.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\verify_end_to_end_certificate.py (Join-Path $Stage "scripts")
Copy-Item .\scripts\export_public_release.py (Join-Path $Stage "scripts")
Copy-Item .\powershell\Run-TwoHost-V6-Evidence.ps1 (Join-Path $Stage "powershell")

Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
$Hash = (Get-FileHash -Algorithm SHA256 $Zip).Hash
Write-Host "CODE_FIDELITY_EVIDENCE=$Zip"
Write-Host "CODE_FIDELITY_EVIDENCE_SHA256=$Hash"
Remove-Item -Recurse -Force $Stage
