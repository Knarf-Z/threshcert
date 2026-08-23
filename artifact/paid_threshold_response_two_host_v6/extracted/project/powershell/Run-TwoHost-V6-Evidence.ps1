$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path .\config\code_manifest.v1.json)) {
    throw "Frozen code manifest missing. Run Initialize-Code-Fidelity after reviewing this source revision."
}

& py -3.11 .\scripts\verify_code_manifest.py
if ($LASTEXITCODE -ne 0) { throw "code-to-manifest fidelity failed" }

& py -3.11 .\scripts\run_code_manifest_mutations.py
if ($LASTEXITCODE -ne 0) { throw "code-manifest mutation matrix failed" }

& py -3.11 .\scripts\extract_restricted_source_inventory.py
if ($LASTEXITCODE -ne 0) { throw "restricted source inventory extraction failed" }

& py -3.11 .\scripts\compiler_bytecode_crosscheck.py
if ($LASTEXITCODE -ne 0) { throw "CPython bytecode cross-check failed" }

& py -3.11 .\scripts\source_coverage_kernel.py
if ($LASTEXITCODE -ne 0) { throw "RSP-V6 source proof failed" }

& py -3.11 .\scripts\run_source_coverage_mutations.py
if ($LASTEXITCODE -ne 0) { throw "source coverage mutation matrix failed" }

& py -3.11 .\scripts\adjudicate_bandit_report.py
if ($LASTEXITCODE -ne 0) { throw "frozen Bandit report adjudication failed" }

& py -3.11 .\scripts\run_capability_certificate.py
if ($LASTEXITCODE -ne 0) { throw "capability certificate generation failed" }

& py -3.11 .\scripts\verify_capability_certificate.py
if ($LASTEXITCODE -ne 0) { throw "capability certificate verification failed" }

& py -3.11 .\scripts\run_coverage_certificate.py
if ($LASTEXITCODE -ne 0) { throw "sealed contract generation failed" }

& py -3.11 .\scripts\verify_coverage_certificate.py
if ($LASTEXITCODE -ne 0) { throw "sealed contract verification failed" }

& .\powershell\Run-TwoHost-Experiment.ps1
if ($LASTEXITCODE -ne 0) { throw "two-host experiment failed" }

& py -3.11 .\scripts\verify_end_to_end_certificate.py
if ($LASTEXITCODE -ne 0) { throw "end-to-end certificate failed" }

& py -3.11 .\scripts\export_public_release.py
if ($LASTEXITCODE -ne 0) { throw "public release export failed" }
Write-Host "TWO_HOST_V6_EVIDENCE=PASS"