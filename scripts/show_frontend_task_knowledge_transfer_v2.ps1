param([ValidateSet('T','E','TE')][string]$Stage='TE')
$ErrorActionPreference='Stop'
$transferRoot=Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe' -B (Join-Path $transferRoot 'repo/ood/issue27frontend_transfer_control_v2.py') status --stage $Stage
if ($LASTEXITCODE -ne 0) { throw 'V2 status verification failed; do not restart.' }
