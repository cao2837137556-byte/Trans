param([ValidateSet('P','T','E','PTE')][string]$Stage = 'PTE')
$ErrorActionPreference = 'Stop'
$transferRoot = Split-Path -Parent $PSScriptRoot
$transferPython = 'C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe'
$env:PYTHONIOENCODING = 'utf-8'
& $transferPython -B (Join-Path $transferRoot 'repo/ood/issue27frontend_transfer_control_v1.py') status --stage $Stage
if ($LASTEXITCODE -ne 0) { throw 'Status verification failed; do not restart the experiment.' }
