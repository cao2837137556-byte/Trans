param([ValidateSet('T','E','TE')][string]$Stage='TE')
$ErrorActionPreference='Stop'
$abstartRoot=Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING='utf-8'
& 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe' -B (Join-Path $abstartRoot 'repo/ood/issue27frontend_abstart_control_v1.py') status --stage $Stage
if ($LASTEXITCODE -ne 0) { throw 'AB-start status verification failed; do not restart.' }
