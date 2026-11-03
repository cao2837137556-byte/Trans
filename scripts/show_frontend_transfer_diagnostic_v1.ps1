$ErrorActionPreference='Stop'
$diagnosticRoot=Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe' -B (Join-Path $diagnosticRoot 'repo/ood/issue27frontend_transfer_diagnostic_v1.py') status
if ($LASTEXITCODE -ne 0) { throw 'Diagnostic status verification failed; do not restart.' }
